/* SPDX-License-Identifier: GPL-2.0 */
/*
 * GBRUNCH: replacements for helpers that the stock Ruby GKI (TRIM_UNUSED_KSYMS) does not export,
 * used by the unmodified upstream ipu-bridge.c. build_gki_modules.py renames the calls in the copied
 * source and includes this header after its own includes. Only exported APIs are used.
 */
#ifndef GBRUNCH_IPU_COMPAT_H
#define GBRUNCH_IPU_COMPAT_H
#include <linux/acpi.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/i2c.h>
#include <linux/property.h>
#include <linux/slab.h>

static inline char *gbrunch_strchrnul(const char *s, int c)
{
	while (*s && *s != (char)c)
		s++;
	return (char *)s;
}

/* set_secondary_fwnode() as in drivers/base/core.c. */
static inline void gbrunch_set_secondary_fwnode(struct device *dev, struct fwnode_handle *fwnode)
{
	if (fwnode)
		fwnode->secondary = ERR_PTR(-ENODEV);
	if (dev->fwnode && !IS_ERR(dev->fwnode->secondary))
		dev->fwnode->secondary = fwnode;
	else
		dev->fwnode = fwnode;
}

static inline int gbrunch_software_node_register_node_group(const struct software_node * const *group)
{
	unsigned int i;
	int ret;

	for (i = 0; group[i]; i++) {
		ret = software_node_register(group[i]);
		if (ret) {
			while (i--)
				software_node_unregister(group[i]);
			return ret;
		}
	}
	return 0;
}

static inline void gbrunch_software_node_unregister_node_group(const struct software_node * const *group)
{
	unsigned int i = 0;

	if (!group)
		return;
	while (group[i])
		i++;
	while (i--)
		software_node_unregister(group[i]);
}

/*
 * software_node_fwnode() of a registered node: a temporary node with a reference property to it,
 * resolved by fwnode_find_reference(). Like the original, the result is not reference counted; the
 * registration keeps the node alive.
 */
static inline struct fwnode_handle *gbrunch_software_node_fwnode(const struct software_node *node)
{
	const struct property_entry props[] = { PROPERTY_ENTRY_REF("gbrunch-node", node), { } };
	struct fwnode_handle *tmp, *fwnode;

	tmp = fwnode_create_software_node(props, NULL);
	if (IS_ERR(tmp))
		return NULL;
	fwnode = fwnode_find_reference(tmp, "gbrunch-node", 0);
	fwnode_remove_software_node(tmp);
	if (IS_ERR(fwnode))
		return NULL;
	fwnode_handle_put(fwnode);
	return fwnode;
}

/*
 * acpi_get_physical_device_location() fills only the panel, the one field ipu-bridge reads, from
 * dword 2 bits 3-5 of the _PLD buffer (ACPI 6.5, 6.1.8). The caller frees it with ACPI_FREE (kfree).
 */
static inline bool gbrunch_acpi_get_physical_device_location(acpi_handle handle, struct acpi_pld_info **pld)
{
	struct acpi_buffer out = { ACPI_ALLOCATE_BUFFER, NULL };
	union acpi_object *obj, *buf;
	bool ok = false;
	u32 dword2;

	if (ACPI_FAILURE(acpi_evaluate_object(handle, "_PLD", NULL, &out)))
		return false;
	obj = out.pointer;
	if (obj && obj->type == ACPI_TYPE_PACKAGE && obj->package.count >= 1) {
		buf = &obj->package.elements[0];
		if (buf->type == ACPI_TYPE_BUFFER && buf->buffer.length >= 12) {
			*pld = kzalloc(sizeof(**pld), GFP_KERNEL);
			if (*pld) {
				memcpy(&dword2, buf->buffer.pointer + 8, sizeof(dword2));
				(*pld)->panel = (le32_to_cpu(dword2) >> 3) & 7;
				ok = true;
			}
		}
	}
	kfree(out.pointer);
	return ok;
}

/* VCM (lens) instantiation: the Dragonfly G4 hi556 is fixed focus; report none. */
static inline struct i2c_client *gbrunch_i2c_find_device_by_fwnode(struct fwnode_handle *fwnode)
{
	return NULL;
}

static inline struct i2c_client *gbrunch_i2c_acpi_new_device_by_fwnode(struct fwnode_handle *fwnode, int index,
								       struct i2c_board_info *info)
{
	return ERR_PTR(-ENODEV);
}
#endif
