/* Offline checks of type enforcement and MLS for explicit contexts/classes. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sepol/policydb/services.h>
int main(int argc,char**argv){
 if(argc!=6)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 3;
 fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);void*d=malloc(n);if(fread(d,1,n,f)!=(size_t)n)return 4;fclose(f);if(sepol_load_policy(d,n))return 5;
 sepol_security_id_t src,dst;sepol_security_class_t cls;sepol_access_vector_t req=0,b;struct sepol_av_decision av;unsigned reason;
 if(sepol_context_to_sid(argv[2],strlen(argv[2])+1,&src)||sepol_context_to_sid(argv[3],strlen(argv[3])+1,&dst)||sepol_string_to_security_class(argv[4],&cls))return 6;
 char*save,*list=strdup(argv[5]);for(char*p=strtok_r(list,",",&save);p;p=strtok_r(NULL,",",&save)){if(sepol_string_to_av_perm(cls,p,&b))return 7;req|=b;}
 if(sepol_compute_av_reason(src,dst,cls,req,&av,&reason))return 8;
 printf("%s -> %s %s %s denied=%08x reason=%x\n",argv[2],argv[3],argv[4],argv[5],req&~av.allowed,reason);return (req&~av.allowed)?1:0;
}
