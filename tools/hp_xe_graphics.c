/* Owned diagnostic: Xe GPU memory-write verification and temporary KMS bars.
 * No filesystem or firmware writes. MIT licensed. */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include "drm.h"
#include "drm_mode.h"
#include "xe_drm.h"
static int call(int fd,unsigned long cmd,void *arg,const char *name){
 if(ioctl(fd,cmd,arg)<0){printf("FAIL %s errno=%d %s\n",name,errno,strerror(errno));return -1;}return 0;
}
static void *query(int fd,uint32_t type){
 struct drm_xe_device_query q={.query=type};
 if(call(fd,DRM_IOCTL_XE_DEVICE_QUERY,&q,"query size")||!q.size||q.size>1048576)return NULL;
 void *p=calloc(1,q.size);if(!p)return NULL;q.data=(uintptr_t)p;
 if(call(fd,DRM_IOCTL_XE_DEVICE_QUERY,&q,"query data")){free(p);return NULL;}return p;
}
static int wait_sync(int fd,uint32_t handle){
 struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
 struct drm_syncobj_wait w={.handles=(uintptr_t)&handle,.count_handles=1,
 .timeout_nsec=(int64_t)t.tv_sec*1000000000+t.tv_nsec+5000000000LL,
 .flags=DRM_SYNCOBJ_WAIT_FLAGS_WAIT_ALL};
 return call(fd,DRM_IOCTL_SYNCOBJ_WAIT,&w,"sync wait (5 second deadline)");
}
static int render(int fd){
 char name[64]={0};struct drm_version v={.name_len=63,.name=name};
 if(call(fd,DRM_IOCTL_VERSION,&v,"driver version"))return 1;
 printf("DRM driver=%s version=%d.%d.%d\n",name,v.version_major,v.version_minor,v.version_patchlevel);
 if(strcmp(name,"xe")){puts("INCONCLUSIVE: Xe is not bound");return 2;}
 struct drm_xe_query_engines *eng=query(fd,DRM_XE_DEVICE_QUERY_ENGINES);
 struct drm_xe_query_mem_regions *mem=query(fd,DRM_XE_DEVICE_QUERY_MEM_REGIONS);
 if(!eng||!mem){free(eng);free(mem);return 1;}
 struct drm_xe_engine_class_instance engine={0};int found=0;uint32_t placement=0;uint64_t size=65536;
 for(uint32_t i=0;i<eng->num_engines;i++){
  struct drm_xe_engine_class_instance e=eng->engines[i].instance;
  printf("ENGINE class=%u instance=%u gt=%u\n",e.engine_class,e.engine_instance,e.gt_id);
  if(!found&&e.engine_class==DRM_XE_ENGINE_CLASS_RENDER){engine=e;found=1;}
 }
 for(uint32_t i=0;i<mem->num_mem_regions;i++){
  printf("MEMORY class=%u instance=%u alignment=%u\n",mem->mem_regions[i].mem_class,mem->mem_regions[i].instance,mem->mem_regions[i].min_page_size);
  if(!placement&&mem->mem_regions[i].mem_class==DRM_XE_MEM_REGION_CLASS_SYSMEM&&mem->mem_regions[i].instance<32){
   placement=1U<<mem->mem_regions[i].instance;
   uint32_t align=mem->mem_regions[i].min_page_size;if(align>size)size=align;
  }
 }
 free(eng);free(mem);if(!found||!placement||size>16777216){puts("INCONCLUSIVE engine/memory selection");return 2;}
 struct drm_xe_vm_create vm={0};if(call(fd,DRM_IOCTL_XE_VM_CREATE,&vm,"VM create"))return 1;
 struct drm_xe_gem_create bo={.vm_id=vm.vm_id,.size=size,.placement=placement,.cpu_caching=DRM_XE_GEM_CPU_CACHING_WC};
 int result=1;void *map=MAP_FAILED;uint32_t bind_handle=0,exec_handle=0,queue=0;
 if(call(fd,DRM_IOCTL_XE_GEM_CREATE,&bo,"GEM create"))goto done;
 struct drm_xe_gem_mmap_offset off={.handle=bo.handle};
 if(call(fd,DRM_IOCTL_XE_GEM_MMAP_OFFSET,&off,"GEM mmap offset"))goto done;
 map=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,off.offset);if(map==MAP_FAILED){perror("GEM mmap");goto done;}
 uint64_t address=0x1000000,target=address+4096;uint32_t expected=0x47584252;
 uint32_t batch[]={0x10000002,(uint32_t)target,(uint32_t)(target>>32),expected,0x05000000,0};
 memcpy(map,batch,sizeof(batch));*(volatile uint32_t *)((char *)map+4096)=0;
 __asm__ __volatile__("sfence" ::: "memory");
 struct drm_syncobj_create obj={0};if(call(fd,DRM_IOCTL_SYNCOBJ_CREATE,&obj,"bind sync create"))goto done;bind_handle=obj.handle;
 obj.handle=0;if(call(fd,DRM_IOCTL_SYNCOBJ_CREATE,&obj,"exec sync create"))goto done;exec_handle=obj.handle;
 struct drm_xe_sync sync={.type=DRM_XE_SYNC_TYPE_SYNCOBJ,.flags=DRM_XE_SYNC_FLAG_SIGNAL,.handle=bind_handle};
 struct drm_xe_vm_bind bind={.vm_id=vm.vm_id,.num_binds=1,.num_syncs=1,.syncs=(uintptr_t)&sync,
 .bind={.obj=bo.handle,.range=size,.addr=address,.pat_index=0,.op=DRM_XE_VM_BIND_OP_MAP}};
 if(call(fd,DRM_IOCTL_XE_VM_BIND,&bind,"VM bind")||wait_sync(fd,bind_handle))goto done;
 struct drm_xe_exec_queue_create q={.vm_id=vm.vm_id,.width=1,.num_placements=1,.instances=(uintptr_t)&engine};
 if(call(fd,DRM_IOCTL_XE_EXEC_QUEUE_CREATE,&q,"render queue create"))goto done;
 queue=q.exec_queue_id;
 sync.handle=exec_handle;
 struct drm_xe_exec exec={.exec_queue_id=queue,.num_syncs=1,.syncs=(uintptr_t)&sync,.address=address,.num_batch_buffer=1};
 if(call(fd,DRM_IOCTL_XE_EXEC,&exec,"GPU batch submit")||wait_sync(fd,exec_handle))goto done;
 __asm__ __volatile__("mfence" ::: "memory");uint32_t got=*(volatile uint32_t *)((char *)map+4096);
 printf("GPU_MEMORY_WRITE expected=%08x actual=%08x\n",expected,got);
 if(got==expected){puts("PASS Xe render-engine command wrote verified data. Shader/Mesa/Vulkan/Android not tested.");result=0;}
 else puts("FAIL GPU memory-write mismatch");
 done:
 if(queue){struct drm_xe_exec_queue_destroy d={.exec_queue_id=queue};ioctl(fd,DRM_IOCTL_XE_EXEC_QUEUE_DESTROY,&d);}
 if(map!=MAP_FAILED)munmap(map,size);
 if(bo.handle){struct drm_gem_close c={.handle=bo.handle};ioctl(fd,DRM_IOCTL_GEM_CLOSE,&c);}
 if(bind_handle){struct drm_syncobj_destroy d={.handle=bind_handle};ioctl(fd,DRM_IOCTL_SYNCOBJ_DESTROY,&d);}
 if(exec_handle){struct drm_syncobj_destroy d={.handle=exec_handle};ioctl(fd,DRM_IOCTL_SYNCOBJ_DESTROY,&d);}
 struct drm_xe_vm_destroy d={.vm_id=vm.vm_id};ioctl(fd,DRM_IOCTL_XE_VM_DESTROY,&d);return result;
}
static int display(int fd){
 if(call(fd,DRM_IOCTL_SET_MASTER,NULL,"DRM master"))return 1;
 struct drm_mode_card_res res={0};uint32_t *connectors=NULL,*crtcs=NULL;int result=2;
 if(call(fd,DRM_IOCTL_MODE_GETRESOURCES,&res,"KMS resources")||res.count_connectors>128||res.count_crtcs>32)goto end;
 connectors=calloc(res.count_connectors+1,4);crtcs=calloc(res.count_crtcs+1,4);if(!connectors||!crtcs)goto end;
 res.connector_id_ptr=(uintptr_t)connectors;res.crtc_id_ptr=(uintptr_t)crtcs;
 uint32_t nc=res.count_connectors,nt=res.count_crtcs;
 res.count_fbs=0;res.count_encoders=0;
 if(call(fd,DRM_IOCTL_MODE_GETRESOURCES,&res,"KMS resource IDs")||res.count_connectors>nc||res.count_crtcs>nt)goto end;
 for(uint32_t i=0;i<res.count_connectors;i++){
  struct drm_mode_get_connector c={.connector_id=connectors[i]};
  if(call(fd,DRM_IOCTL_MODE_GETCONNECTOR,&c,"force connector probe"))continue;
  printf("CONNECTOR id=%u type=%u connection=%u modes=%u encoders=%u\n",c.connector_id,c.connector_type,c.connection,c.count_modes,c.count_encoders);
  if(!c.count_modes||c.count_modes>256||c.count_encoders>64)continue;
  struct drm_mode_modeinfo *modes=calloc(c.count_modes,sizeof(*modes));uint32_t *enc=calloc(c.count_encoders+1,4);
  if(!modes||!enc){free(modes);free(enc);continue;}c.modes_ptr=(uintptr_t)modes;c.encoders_ptr=(uintptr_t)enc;
  uint32_t nm=c.count_modes,ne=c.count_encoders;c.count_props=0;
  if(call(fd,DRM_IOCTL_MODE_GETCONNECTOR,&c,"connector modes")||c.count_modes>nm||c.count_encoders>ne){free(modes);free(enc);continue;}
  for(uint32_t j=0;j<c.count_modes;j++)printf("MODE %s %ux%u refresh=%u type=%x\n",modes[j].name,modes[j].hdisplay,modes[j].vdisplay,modes[j].vrefresh,modes[j].type);
  /* Prefer the internal eDP panel; do not reconfigure external monitors. */
  if(c.connector_type!=DRM_MODE_CONNECTOR_eDP||c.connection!=1){free(modes);free(enc);continue;}
  uint32_t crtc=0;for(uint32_t j=0;j<c.count_encoders&&!crtc;j++){
   struct drm_mode_get_encoder e={.encoder_id=enc[j]};if(ioctl(fd,DRM_IOCTL_MODE_GETENCODER,&e))continue;
   if(e.crtc_id)crtc=e.crtc_id;else for(uint32_t k=0;k<res.count_crtcs;k++)if(e.possible_crtcs&(1U<<k)){crtc=crtcs[k];break;}
  }
  uint32_t mi=0;for(uint32_t j=0;j<c.count_modes;j++)if(modes[j].type&DRM_MODE_TYPE_PREFERRED){mi=j;break;}
  struct drm_mode_modeinfo mode=modes[mi];free(modes);free(enc);if(!crtc)continue;
  struct drm_mode_crtc old={.crtc_id=crtc};if(call(fd,DRM_IOCTL_MODE_GETCRTC,&old,"save CRTC"))continue;
  struct drm_mode_create_dumb bo={.width=mode.hdisplay,.height=mode.vdisplay,.bpp=32};
  if(call(fd,DRM_IOCTL_MODE_CREATE_DUMB,&bo,"scanout buffer create"))continue;
  struct drm_mode_map_dumb off={.handle=bo.handle};void *map=MAP_FAILED;uint32_t fb=0;
  if(call(fd,DRM_IOCTL_MODE_MAP_DUMB,&off,"scanout map offset"))goto clean;
  map=mmap(NULL,bo.size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,off.offset);if(map==MAP_FAILED){perror("scanout mmap");goto clean;}
  const uint32_t colors[]={0xff0000,0x00ff00,0x0000ff,0xffffff,0xffff00,0x00ffff,0xff00ff,0x101010};
  for(uint32_t y=0;y<bo.height;y++)for(uint32_t x=0;x<bo.width;x++)*((uint32_t *)((char *)map+y*bo.pitch)+x)=colors[(uint64_t)x*8/bo.width];
  __asm__ __volatile__("sfence" ::: "memory");
  struct drm_mode_fb_cmd add={.width=bo.width,.height=bo.height,.pitch=bo.pitch,.bpp=32,.depth=24,.handle=bo.handle};
  if(call(fd,DRM_IOCTL_MODE_ADDFB,&add,"add framebuffer"))goto clean;
  fb=add.fb_id;
  uint32_t conn=c.connector_id;struct drm_mode_crtc set={.crtc_id=crtc,.fb_id=fb,.set_connectors_ptr=(uintptr_t)&conn,.count_connectors=1,.mode_valid=1,.mode=mode};
  if(call(fd,DRM_IOCTL_MODE_SETCRTC,&set,"show color bars"))goto clean;
  puts("PASS KMS accepted color-bar modeset; physical visibility requires user confirmation. Holding 8 seconds.");result=0;sleep(8);
  old.set_connectors_ptr=(uintptr_t)&conn;old.count_connectors=old.mode_valid?1:0;
  if(call(fd,DRM_IOCTL_MODE_SETCRTC,&old,"restore display"))puts("WARN display restore failed; shutdown will follow");
  clean:
  if(fb)ioctl(fd,DRM_IOCTL_MODE_RMFB,&fb);
  if(map!=MAP_FAILED)munmap(map,bo.size);
  struct drm_mode_destroy_dumb destroy={.handle=bo.handle};ioctl(fd,DRM_IOCTL_MODE_DESTROY_DUMB,&destroy);break;
 }
 if(result==2)puts("INCONCLUSIVE: no connected internal panel with usable modes");
 end:free(connectors);free(crtcs);ioctl(fd,DRM_IOCTL_DROP_MASTER,NULL);return result;
}
int main(int argc,char **argv){
 setvbuf(stdout,NULL,_IONBF,0);if(argc!=3)return 2;int fd=open(argv[2],O_RDWR|O_CLOEXEC);if(fd<0){perror(argv[2]);return 1;}
 int rc=!strcmp(argv[1],"render")?render(fd):!strcmp(argv[1],"display")?display(fd):2;close(fd);return rc;
}
