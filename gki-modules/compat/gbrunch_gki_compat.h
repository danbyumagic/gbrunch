/* SPDX-License-Identifier: GPL-2.0 */
/*
 * GBRUNCH: replacements for helpers that the stock Ruby GKI (TRIM_UNUSED_KSYMS) does not export,
 * used by unmodified upstream CS35L41 HDA sources. build_gki_modules.py renames the calls in
 * the copied sources and includes this header after their own includes.
 */
#ifndef GBRUNCH_GKI_COMPAT_H
#define GBRUNCH_GKI_COMPAT_H
#include <linux/gpio/consumer.h>
#include <linux/property.h>
#include <linux/err.h>

/* gpiod_get_index() resolves ACPI GPIOs (including _DSD/driver mappings) through the fwnode;
 * fwnode_gpiod_get_index() takes the same path and is exported. */
static inline struct gpio_desc *gbrunch_gpiod_get_index(struct device *dev, const char *con_id,
							unsigned int idx, enum gpiod_flags flags)
{
	return fwnode_gpiod_get_index(dev_fwnode(dev), con_id, idx, flags, dev_name(dev));
}

static inline int gbrunch_gpiod_count(struct device *dev, const char *con_id)
{
	struct gpio_desc *d;
	int n = 0;

	while (!IS_ERR(d = fwnode_gpiod_get_index(dev_fwnode(dev), con_id, n, GPIOD_ASIS, NULL))) {
		gpiod_put(d);
		n++;
	}
	return n ? n : -ENOENT;
}

/*
 * Amplifier error interrupts without regmap-irq's domain: regmap_irq_get_virq() and
 * regmap_irq_get_domain() are not exported. Each amplifier instead requests the shared ACPI GpioInt
 * once (IRQF_SHARED, as upstream) with a thread that does regmap-irq's work: resume the amplifier,
 * read each status register once, acknowledge the enabled bits that are set, and call the upstream
 * handler of each. The upstream handlers then record irq_errors, and the driver's own error release
 * runs at the next pause, as on mainline. "data" is this header's own struct, never regmap's.
 */
#include <linux/interrupt.h>
#include <linux/pm_runtime.h>
#include <linux/regmap.h>

#define GBRUNCH_IRQ_REGS 4	/* CS35L41 IRQ1_STATUS1..4, register stride 4 */

struct gbrunch_irq_chip {
	struct device *dev;
	struct regmap *map;
	const struct regmap_irq_chip *chip;
	irq_handler_t *handlers;	/* by regmap IRQ index */
	void *dev_id;
	unsigned int enabled[GBRUNCH_IRQ_REGS];
	bool requested;
};

static inline int gbrunch_devm_regmap_add_irq_chip(struct device *dev, struct regmap *map, int irq,
						   int irq_flags, int irq_base,
						   const struct regmap_irq_chip *chip,
						   struct regmap_irq_chip_data **data)
{
	struct gbrunch_irq_chip *c;

	if (irq <= 0 || chip->num_regs > GBRUNCH_IRQ_REGS)
		return -EINVAL;
	c = devm_kzalloc(dev, sizeof(*c), GFP_KERNEL);
	if (!c)
		return -ENOMEM;
	c->handlers = devm_kcalloc(dev, chip->num_irqs, sizeof(*c->handlers), GFP_KERNEL);
	if (!c->handlers)
		return -ENOMEM;
	c->dev = dev;
	c->map = map;
	c->chip = chip;
	*data = (struct regmap_irq_chip_data *)c;
	return 0;
}

/* The line is shared by every amplifier; the request below needs the line, not a virq. */
#define gbrunch_regmap_irq_get_virq(data, hwirq) (cs35l41->irq)

static irqreturn_t gbrunch_regmap_irq_thread(int irq, void *p)
{
	struct gbrunch_irq_chip *c = p;
	const struct regmap_irq_chip *chip = c->chip;
	unsigned int status[GBRUNCH_IRQ_REGS] = { 0 };
	irqreturn_t ret = IRQ_NONE;
	int r, i;

	if (pm_runtime_resume_and_get(c->dev) < 0)
		return IRQ_NONE;
	for (r = 0; r < chip->num_regs; r++) {
		if (!c->enabled[r] || regmap_read(c->map, chip->status_base + 4 * r, &status[r]))
			continue;
		status[r] &= c->enabled[r];
		if (status[r])
			regmap_write(c->map, chip->ack_base + 4 * r, status[r]);
	}
	for (i = 0; i < chip->num_irqs; i++) {
		const struct regmap_irq *ri = &chip->irqs[i];

		if (c->handlers[i] && (status[ri->reg_offset / 4] & ri->mask) &&
		    c->handlers[i](irq, c->dev_id) == IRQ_HANDLED)
			ret = IRQ_HANDLED;
	}
	pm_runtime_put(c->dev);
	return ret;
}

static inline int gbrunch_request_regmap_irq(struct regmap_irq_chip_data *data, int hwirq,
					     struct device *dev, unsigned int irq,
					     irq_handler_t primary, irq_handler_t thread,
					     unsigned long flags, const char *name, void *dev_id)
{
	struct gbrunch_irq_chip *c = (struct gbrunch_irq_chip *)data;
	const struct regmap_irq *ri = &c->chip->irqs[hwirq];
	unsigned int r = ri->reg_offset / 4;
	int ret;

	if (hwirq < 0 || hwirq >= c->chip->num_irqs || r >= c->chip->num_regs || primary)
		return -EINVAL;
	if (!c->requested) {
		ret = devm_request_threaded_irq(dev, irq, NULL, gbrunch_regmap_irq_thread, flags,
						dev_name(dev), c);
		if (ret)
			return ret;
		c->requested = true;
	}
	c->dev_id = dev_id;
	c->handlers[hwirq] = thread;
	c->enabled[r] |= ri->mask;
	regmap_write(c->map, c->chip->ack_base + ri->reg_offset, ri->mask);	/* drop a stale latch */
	return regmap_update_bits(c->map, c->chip->mask_base + ri->reg_offset, ri->mask, 0);
}

/* Firmware load vs. system suspend serialisation is not available to modules here. */
static inline unsigned int gbrunch_lock_system_sleep(void) { return 0; }
static inline void gbrunch_unlock_system_sleep(unsigned int flags) { (void)flags; }
/* component_add() is a protected export (only signed GKI modules may use it); component_add_typed()
 * is not. The subcomponent value is only consulted by typed matchers; hda_component matches untyped
 * by device name, so registering as subcomponent 1 binds identically. */
#include <linux/component.h>
static inline int gbrunch_component_add(struct device *dev, const struct component_ops *ops)
{
	return component_add_typed(dev, ops, 1);
}
#endif
