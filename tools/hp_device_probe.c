/* Small Intel GPU command-submission, read-only NVMe health and USB read tests. */
#include <errno.h>
#include <fcntl.h>
#include <linux/nvme_ioctl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include "drm.h"
#include "i915_drm.h"
static int gpu(int fd){
 char name[64]={0};struct drm_version v={.name_len=sizeof(name)-1,.name=name};
 if(ioctl(fd,DRM_IOCTL_VERSION,&v)){perror("DRM_VERSION");return 1;}
 printf("DRM driver=%s version=%d.%d.%d\n",name,v.version_major,v.version_minor,v.version_patchlevel);
 if(strcmp(name,"i915")){puts("SKIP Intel i915 submission: another DRM driver");return 0;}
 int id=0;struct drm_i915_getparam param={.param=I915_PARAM_CHIPSET_ID,.value=&id};
 if(!ioctl(fd,DRM_IOCTL_I915_GETPARAM,&param))printf("Intel chipset ID=%04x\n",id);
 struct drm_i915_gem_create create={.size=4096};if(ioctl(fd,DRM_IOCTL_I915_GEM_CREATE,&create)){perror("GEM_CREATE");return 1;}
 uint32_t commands[2]={0x05000000,0}; /* MI_BATCH_BUFFER_END and padding */
 struct drm_i915_gem_pwrite write={.handle=create.handle,.size=sizeof(commands),.data_ptr=(uintptr_t)commands};
 int result=1;
 if(ioctl(fd,DRM_IOCTL_I915_GEM_PWRITE,&write)){
  if(errno!=EOPNOTSUPP&&errno!=EINVAL){perror("GEM_PWRITE");goto done;}
  puts("Legacy GEM_PWRITE unsupported; using modern GEM_MMAP_OFFSET.");
  struct drm_i915_gem_mmap_offset offset={.handle=create.handle,.flags=I915_MMAP_OFFSET_FIXED};
  if(ioctl(fd,DRM_IOCTL_I915_GEM_MMAP_OFFSET,&offset)){
   offset.flags=I915_MMAP_OFFSET_WB;
   if(ioctl(fd,DRM_IOCTL_I915_GEM_MMAP_OFFSET,&offset)){perror("GEM_MMAP_OFFSET");goto done;}
  }
  void*map=mmap(NULL,4096,PROT_READ|PROT_WRITE,MAP_SHARED,fd,offset.offset);
  if(map==MAP_FAILED){perror("mmap GEM");goto done;}
  memcpy(map,commands,sizeof(commands));__sync_synchronize();munmap(map,4096);
 }
 struct drm_i915_gem_exec_object2 object={.handle=create.handle};
 struct drm_i915_gem_execbuffer2 exec={.buffers_ptr=(uintptr_t)&object,.buffer_count=1,.batch_len=sizeof(commands),.flags=I915_EXEC_RENDER};
 if(ioctl(fd,DRM_IOCTL_I915_GEM_EXECBUFFER2,&exec)){perror("EXECBUFFER2");goto done;}
 struct drm_i915_gem_wait wait={.bo_handle=create.handle,.timeout_ns=2000000000LL};
 if(ioctl(fd,DRM_IOCTL_I915_GEM_WAIT,&wait)){perror("GEM_WAIT");goto done;}
 puts("PASS Intel GPU no-op command submitted and completed. Mesa/Vulkan/Android compositor not tested.");result=0;
 done:;struct drm_gem_close close={.handle=create.handle};ioctl(fd,DRM_IOCTL_GEM_CLOSE,&close);return result;
}
static int nvme(int fd){
 unsigned char data[512]={0};struct nvme_admin_cmd command={.opcode=2,.nsid=0xffffffff,.addr=(uintptr_t)data,.data_len=sizeof(data),.cdw10=(127U<<16)|2,.timeout_ms=3000};
 int rc=ioctl(fd,NVME_IOCTL_ADMIN_CMD,&command);if(rc){printf("NVMe GET_LOG_PAGE status=%d errno=%d\n",rc,errno);return 1;}
 printf("PASS read-only NVMe SMART query: critical_warning=0x%02x temperature_kelvin=%u spare_percent=%u percent_used=%u\n",data[0],data[1]|data[2]<<8,data[3],data[5]);
 printf("media_errors_u128_le=");for(int i=175;i>=160;i--)printf("%02x",data[i]);puts("");return 0;
}
static int storage(int fd){
 char data[65536];unsigned long total=0;struct timespec a,b;clock_gettime(CLOCK_MONOTONIC,&a);
 while(total<16UL*1024*1024){ssize_t n=read(fd,data,sizeof(data));if(n<=0){if(n<0)perror("read storage");break;}total+=n;}
 clock_gettime(CLOCK_MONOTONIC,&b);double sec=(b.tv_sec-a.tv_sec)+(b.tv_nsec-a.tv_nsec)/1e9;
 printf("READ_ONLY sample_bytes=%lu seconds=%.6f approx_MiB_per_second=%.2f cached_and_not_full_bandwidth_test=1\n",total,sec,total/1048576.0/sec);return total==16UL*1024*1024?0:1;
}
int main(int argc,char**argv){
 if(argc!=3)return 2;int fd=open(argv[2],!strcmp(argv[1],"gpu")?O_RDWR:O_RDONLY);if(fd<0){perror(argv[2]);return 1;}
 int rc=!strcmp(argv[1],"gpu")?gpu(fd):!strcmp(argv[1],"nvme")?nvme(fd):!strcmp(argv[1],"storage")?storage(fd):2;close(fd);return rc;
}
