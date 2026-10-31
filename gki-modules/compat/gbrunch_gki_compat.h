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
 * regmap_irq_get_domain() are not exported. Each upstream error handler is instead requested on
 * the shared ACPI GpioInt itself (IRQF_SHARED, as upstream), behind a thread that runs it only
 * when its own status bit is latched, acknowledges that bit (as regmap-irq does) and unmasks it at
 * request time. The upstream handlers then record irq_errors, and the driver's own error release
 * runs at the next pause, as on mainline. "data" is this header's own struct, never regmap's.
 */
#include <linux/interrupt.h>
#include <linux/pm_runtime.h>
#include <linux/regmap.h>

struct gbrunch_irq_chip {
	struct regmap *map;
	const struct regmap_irq_chip *chip;
};

struct gbrunch_irq_src {
	struct device *dev;
	struct regmap *map;
	unsigned int status, mask;
	irq_handler_t handler;
	void *dev_id;
};

static inline int gbrunch_devm_regmap_add_irq_chip(struct device *dev, struct regmap *map, int irq,
						   int irq_flags, int irq_base,
						   const struct regmap_irq_chip *chip,
						   struct regmap_irq_chip_data **data)
{
	struct gbrunch_irq_chip *c;

	if (irq <= 0)
		return -EINVAL;
	c = devm_kzalloc(dev, sizeof(*c), GFP_KERNEL);
	if (!c)
		return -ENOMEM;
	c->map = map;
	c->chip = chip;
	*data = (struct regmap_irq_chip_data *)c;
	return 0;
}

/* The line is shared by every amplifier; the request below needs the line, not a virq. */
#define gbrunch_regmap_irq_get_virq(data, hwirq) (cs35l41->irq)

static irqreturn_t gbrunch_regmap_irq_thread(int irq, void *p)
{
	struct gbrunch_irq_src *s = p;
	irqreturn_t ret = IRQ_NONE;
	unsigned int v;

	if (pm_runtime_get_if_active(s->dev) <= 0)
		return IRQ_NONE;	/* a suspended amplifier has no latched error to report */
	if (!regmap_read(s->map, s->status, &v) && (v & s->mask)) {
		regmap_write(s->map, s->status, s->mask);
		ret = s->handler(irq, s->dev_id);
	}
	pm_runtime_put(s->dev);
	return ret;
}

static inline int gbrunch_request_regmap_irq(struct regmap_irq_chip_data *data, int hwirq,
					     struct device *dev, unsigned int irq,
					     irq_handler_t primary, irq_handler_t thread,
					     unsigned long flags, const char *name, void *dev_id)
{
	struct gbrunch_irq_chip *c = (struct gbrunch_irq_chip *)data;
	const struct regmap_irq *ri = &c->chip->irqs[hwirq];
	struct gbrunch_irq_src *s;
	int ret;

	s = devm_kzalloc(dev, sizeof(*s), GFP_KERNEL);
	if (!s)
		return -ENOMEM;
	*s = (struct gbrunch_irq_src){ .dev = dev, .map = c->map, .handler = thread, .dev_id = dev_id,
		.status = c->chip->status_base + ri->reg_offset, .mask = ri->mask };
	regmap_write(s->map, s->status, s->mask);	/* drop a stale latch before unmasking */
	ret = devm_request_threaded_irq(dev, irq, primary, gbrunch_regmap_irq_thread, flags, name, s);
	if (!ret)
		ret = regmap_update_bits(s->map, c->chip->mask_base + ri->reg_offset, s->mask, 0);
	return ret;
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
