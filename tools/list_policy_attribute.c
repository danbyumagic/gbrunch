/* Read-only enumeration of concrete members of an existing SELinux attribute. */
#include <stdio.h>
#include <sepol/policydb/policydb.h>
#include <sepol/policydb/hashtab.h>
int main(int argc,char**argv){
 if(argc!=3)return 2;policydb_t p;policy_file_t f;policydb_init(&p);policy_file_init(&f);f.type=PF_USE_STDIO;f.fp=fopen(argv[1],"rb");if(!f.fp||policydb_read(&p,&f,0))return 3;fclose(f.fp);
 type_datum_t*a=hashtab_search(p.p_types.table,argv[2]);if(!a||a->flavor!=TYPE_ATTRIB)return 4;
 for(unsigned i=0;i<p.p_types.nprim;i++)if(p.type_val_to_struct[i]&&p.type_val_to_struct[i]->flavor==TYPE_TYPE&&ebitmap_get_bit(&p.type_attr_map[i],a->s.value-1))puts(p.p_type_val_to_name[i]);
 policydb_destroy(&p);return 0;
}
