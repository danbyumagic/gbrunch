// SPDX-License-Identifier: GPL-2.0
/*
 * GBRUNCH: connect ACPI-described camera sensors to the stock IPU6 driver.
 *
 * Ruby's intel-ipu6.ko is built with CONFIG_IPU_BRIDGE=n, so its probe never builds the software-node
 * graph from the sensors' ACPI SSDB data. ipu-isys then registers no sensor, and the sensor driver
 * (hi556 on the HP Dragonfly G4) waits forever for its fwnode endpoint. This module runs the upstream
 * ipu-bridge (built unmodified beside it) on each IPU6 PCI device. ipu_bridge_init() sets the graph as
 * the device's secondary fwnode. The stock driver uses it after a rebind, which init does on boot.
 */
#include <linux/module.h>
#include <linux/pci.h>
#include <media/ipu-bridge.h>
#include <media/ipu6-pci-table.h>

static int __init gbrunch_ipu6_bridge_init(void)
{
	const struct pci_device_id *id;
	struct pci_dev *pdev;
	int ret;

	for (id = ipu6_pci_tbl; id->vendor; id++) {
		pdev = NULL;
		while ((pdev = pci_get_device(id->vendor, id->device, pdev))) {
			ret = ipu_bridge_init(&pdev->dev, ipu_bridge_parse_ssdb);
			if (ret)
				dev_warn(&pdev->dev, "GBRUNCH: ipu-bridge init failed: %d\n", ret);
			else
				dev_info(&pdev->dev, "GBRUNCH: ipu-bridge graph ready; rebind intel-ipu6 to use it\n");
		}
	}
	return 0;
}
module_init(gbrunch_ipu6_bridge_init);

MODULE_DESCRIPTION("GBRUNCH: ipu-bridge for the stock IPU6 driver (built without CONFIG_IPU_BRIDGE)");
MODULE_LICENSE("GPL");
MODULE_IMPORT_NS("INTEL_IPU_BRIDGE");
