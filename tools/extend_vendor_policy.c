/* Extend only listed access-vector rules in a locally generated vendor view.
 * No permissive domains, policy capabilities, constraints or MLS changes.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sepol/policydb/policydb.h>
#include <sepol/policydb/hashtab.h>
#include <sepol/policydb/avtab.h>
int main(int argc,char**argv){
 if(argc<7||(argc-3)%4){fprintf(stderr,"input output source target class comma-permissions [repeat]\n");return 2;}
 policydb_t p;policy_file_t f;policydb_init(&p);policy_file_init(&f);f.type=PF_USE_STDIO;
 f.fp=fopen(argv[1],"rb");if(!f.fp||policydb_read(&p,&f,0))return 3;fclose(f.fp);
 for(int i=3;i<argc;i+=4){
  type_datum_t*s=hashtab_search(p.p_types.table,argv[i]),*t=hashtab_search(p.p_types.table,argv[i+1]);
  class_datum_t*c=hashtab_search(p.p_classes.table,argv[i+2]);
  if(!s||!t||!c){fprintf(stderr,"Unknown type/class: %s %s %s\n",argv[i],argv[i+1],argv[i+2]);return 4;}
  unsigned bits=0;char*perms=strdup(argv[i+3]);char*save;
  for(char*v=strtok_r(perms,",",&save);v;v=strtok_r(NULL,",",&save)){
   perm_datum_t*d=hashtab_search(c->permissions.table,v);if(!d&&c->comdatum)d=hashtab_search(c->comdatum->permissions.table,v);
   if(!d||!d->s.value||d->s.value>32){fprintf(stderr,"Unknown permission %s\n",v);return 5;}bits|=1U<<(d->s.value-1);
  }free(perms);
  avtab_key_t key={.source_type=s->s.value,.target_type=t->s.value,.target_class=c->s.value,.specified=AVTAB_ALLOWED};
  avtab_datum_t*old=avtab_search(&p.te_avtab,&key);
  printf("allow %s %s:%s {%s}; added_bits=%08x\n",argv[i],argv[i+1],argv[i+2],argv[i+3],bits&~(old?old->data:0));
  if(old)old->data|=bits;else{avtab_datum_t value={.data=bits};if(avtab_insert(&p.te_avtab,&key,&value))return 6;}
 }
 f.fp=fopen(argv[2],"wb");if(!f.fp||policydb_write(&p,&f))return 7;fclose(f.fp);policydb_destroy(&p);return 0;
}
