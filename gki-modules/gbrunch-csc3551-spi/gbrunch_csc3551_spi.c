// SPDX-License-Identifier: GPL-2.0
/*
 * GBRUNCH: instantiate the SPI CS35L41 amplifiers described by an ACPI CSC3551 node.
 *
 * Upstream does this in serial-multi-instantiate, which needs acpi_spi_device_alloc() and
 * spi_add_device(). The stock GKI does not export either. This driver parses the node's
 * SpiSerialBus resources, finds the controller from the resource source path, and creates each
 * device with the exported spi_new_device(), with the node's shared GpioInt as its IRQ. It then
 * gives the device the name that serial-multi-instantiate would use:
 * "<ctlr>-<acpi dev>-cs35l41-hda.<i>". cs35l41-hda (SPI) and the HDA component matcher both rely
 * on that name, so this module must be loaded before the cs35l41 SPI driver.
 *
 * Like acpi_spi_device_alloc(), each device gets the CSC3551 node as its firmware node. The SPI
 * core needs it: for an ACPI node, GPIO chip selects are driven with SPI-level polarity. HP
 * describes CS1-3 as controller "cs-gpios" pointing at this node's GpioIo entries (ACS1-3).
 * Without the node they were driven inverted, so only the native-CS0 amplifier answered.

 */
#include <linux/acpi.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/spi/spi.h>

#define MAX_AMPS 4

struct csc_spi_res {
	char ctlr_path[64];
	u16 cs;
	u32 speed;
	u32 mode;
};

struct csc_ctx {
	struct csc_spi_res res[MAX_AMPS];
	int count;
};

struct csc_priv {
	struct spi_device *spi[MAX_AMPS];
	int count;
};

static int csc_collect(struct acpi_resource *ares, void *data)
{
	struct csc_ctx *ctx = data;
	struct acpi_resource_spi_serialbus *sb;
	struct csc_spi_res *r;

	if (ares->type != ACPI_RESOURCE_TYPE_SERIAL_BUS)
		return 1;
	sb = &ares->data.spi_serial_bus;
	if (sb->type != ACPI_RESOURCE_SERIAL_TYPE_SPI || ctx->count >= MAX_AMPS)
		return 1;
	r = &ctx->res[ctx->count++];
	strscpy(r->ctlr_path, sb->resource_source.string_ptr ?: "", sizeof(r->ctlr_path));
	r->cs = sb->device_selection;
	r->speed = sb->connection_speed;
	r->mode = (sb->clock_polarity == ACPI_SPI_START_HIGH ? SPI_CPOL : 0) |
		  (sb->clock_phase == ACPI_SPI_SECOND_PHASE ? SPI_CPHA : 0) |
		  (sb->wire_mode == ACPI_SPI_3WIRE_MODE ? SPI_3WIRE : 0) |
		  (sb->device_polarity == ACPI_SPI_ACTIVE_HIGH ? SPI_CS_HIGH : 0);
	return 1;
}

static int csc_is_ctlr(struct device *dev, void *data)
{
	struct device **found = data;

	if (dev->class && !strcmp(dev->class->name, "spi_master")) {
		*found = dev;
		return 1;
	}
	return device_for_each_child(dev, data, csc_is_ctlr);
}

static struct spi_controller *csc_find_ctlr(const char *path)
{
	struct acpi_device *cadev;
	struct device *phys, *found = NULL;
	acpi_handle h;

	if (ACPI_FAILURE(acpi_get_handle(NULL, (acpi_string)path, &h)))
		return NULL;
	cadev = acpi_fetch_acpi_dev(h);
	if (!cadev)
		return NULL;
	phys = acpi_get_first_physical_node(cadev);
	if (!phys)
		return NULL;
	device_for_each_child(phys, &found, csc_is_ctlr);
	if (!found)
		return NULL;
	get_device(found);
	return container_of(found, struct spi_controller, dev);
}

static int csc_probe(struct platform_device *pdev)
{
	struct acpi_device *adev = ACPI_COMPANION(&pdev->dev);
	struct csc_ctx ctx = { 0 };
	struct csc_priv *priv;
	struct spi_controller *ctlr;
	LIST_HEAD(list);
	int i, ret, irq;

	if (!adev)
		return -ENODEV;
	ret = acpi_dev_get_resources(adev, &list, csc_collect, &ctx);
	if (ret < 0)
		return ret;
	acpi_dev_free_resource_list(&list);
	if (!ctx.count)
		return -ENOENT;

	/* Like serial-multi-instantiate's IRQ_RESOURCE_AUTO: every amplifier shares GpioInt 0 (INTB). */
	irq = acpi_dev_gpio_irq_get(adev, 0);
	if (irq == -EPROBE_DEFER)
		return irq;
	if (irq < 0) {
		dev_warn(&pdev->dev, "no amplifier interrupt: %d\n", irq);
		irq = 0;
	}

	priv = devm_kzalloc(&pdev->dev, sizeof(*priv), GFP_KERNEL);
	if (!priv)
		return -ENOMEM;

	for (i = 0; i < ctx.count; i++) {
		struct spi_board_info bi = {
			.max_speed_hz = ctx.res[i].speed,
			.chip_select = ctx.res[i].cs,
			.mode = ctx.res[i].mode,
			.irq = irq,
		};
		struct spi_device *spi;
		char name[64];

		ctlr = csc_find_ctlr(ctx.res[i].ctlr_path);
		if (!ctlr) {
			ret = -EPROBE_DEFER;
			goto err;
		}
		strscpy(bi.modalias, "cs35l41-hda", sizeof(bi.modalias));
		spi = spi_new_device(ctlr, &bi);
		snprintf(name, sizeof(name), "%s-%s-cs35l41-hda.%d", dev_name(&ctlr->dev),
			 dev_name(&adev->dev), i);
		put_device(&ctlr->dev);
		if (!spi) {
			ret = -ENODEV;
			goto err;
		}
		priv->spi[priv->count++] = spi;
		device_set_node(&spi->dev, acpi_fwnode_handle(adev));
		ret = spi_setup(spi);	/* re-apply the inactive CS level with ACPI polarity */
		if (ret)
			goto err;
		ret = device_rename(&spi->dev, name);
		if (ret)
			goto err;
		dev_info(&pdev->dev, "%s: cs %u, %u Hz, mode 0x%x, irq %d\n", name, ctx.res[i].cs,
			 ctx.res[i].speed, ctx.res[i].mode, irq);
	}
	platform_set_drvdata(pdev, priv);
	return 0;
err:
	while (priv->count--)
		device_unregister(&priv->spi[priv->count]->dev);
	return dev_err_probe(&pdev->dev, ret, "CSC3551 SPI instantiation failed\n");
}

static void csc_remove(struct platform_device *pdev)
{
	struct csc_priv *priv = platform_get_drvdata(pdev);

	while (priv->count--)
		device_unregister(&priv->spi[priv->count]->dev);
}

static const struct acpi_device_id csc_acpi_ids[] = {
	{ "CSC3551", 0 },
	{ }
};
MODULE_DEVICE_TABLE(acpi, csc_acpi_ids);

static struct platform_driver csc_driver = {
	.driver = {
		.name = "gbrunch-csc3551-spi",
		.acpi_match_table = csc_acpi_ids,
	},
	.probe = csc_probe,
	.remove = csc_remove,
};
module_platform_driver(csc_driver);

MODULE_DESCRIPTION("GBRUNCH: SPI instantiation for ACPI CSC3551 (CS35L41) amplifiers");
MODULE_LICENSE("GPL");
