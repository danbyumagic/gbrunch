/* Offline SELinux access checks include type enforcement and MLS constraints. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sepol/policydb/services.h>
int main(int argc,char **argv) {
 if(argc<2)return 2;
 FILE*f=fopen(argv[1],"rb");if(!f)return 3;
 fseek(f,0,SEEK_END);long len=ftell(f);rewind(f);void*data=malloc(len);
 if(fread(data,1,len,f)!=(size_t)len)return 4;fclose(f);
 if(sepol_load_policy(data,len))return 5;free(data);
 sepol_security_class_t cls;sepol_access_vector_t requested=0,b;
 if(sepol_string_to_security_class("memfd_file",&cls))return 6;
 const char *perms[]={"read","write","getattr","map"};
 for(int i=0;i<4;i++){if(sepol_string_to_av_perm(cls,perms[i],&b))return 7;requested|=b;}
 const char*defaults[]={"u:r:platform_app:s0:c512,c768","u:r:priv_app:s0:c522,c768","u:r:priv_app_36:s0:c522,c768","u:r:system_app:s0","u:r:gmscore_app:s0:c522,c768","u:r:untrusted_app:s0:c522,c768","u:r:isolated_app:s0:c522,c768"};
 const char**contexts=argc>2?(const char**)&argv[2]:defaults;
 int count=argc>2?argc-2:7;
 const char *target="u:object_r:hal_graphics_allocator_default:s0";
 sepol_security_id_t tsid;if(sepol_context_to_sid(target,strlen(target)+1,&tsid))return 8;
 for(int i=0;i<count;i++){
  sepol_security_id_t ssid;struct sepol_av_decision av;unsigned reason=0;
  if(sepol_context_to_sid(contexts[i],strlen(contexts[i])+1,&ssid))return 9;
  if(sepol_compute_av_reason(ssid,tsid,cls,requested,&av,&reason))return 10;
  printf("%s requested=%08x allowed=%08x denied=%08x reason=%x\n",contexts[i],requested,av.allowed&requested,requested&~av.allowed,reason);
 }
 return 0;
}
