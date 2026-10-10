/* Mocked UAPI sequence/error-path test. Does NOT test hardware. */
#define ioctl mock_ioctl
#define mmap mock_mmap
#define munmap mock_munmap
#define sleep mock_sleep
#define main diagnostic_main
#include "hp_xe_graphics.c"
#undef main
#undef ioctl
#undef mmap
#undef munmap
#undef sleep
#include <assert.h>
#include <stdarg.h>
static void *mapping;
static int fail_bind,no_modes,executions,shows,restores;
void *mock_mmap(void *a,size_t n,int p,int f,int fd,off_t o){
 (void)a;(void)p;(void)f;(void)fd;(void)o;mapping=calloc(1,n);return mapping;
}
int mock_munmap(void *a,size_t n){(void)n;free(a);mapping=NULL;return 0;}
unsigned int mock_sleep(unsigned int s){assert(s==8);return 0;}
int mock_ioctl(int fd,unsigned long cmd,...){
 (void)fd;va_list ap;va_start(ap,cmd);void *arg=va_arg(ap,void *);va_end(ap);
 if(cmd==DRM_IOCTL_VERSION){struct drm_version *v=arg;strcpy(v->name,"xe");return 0;}
 if(cmd==DRM_IOCTL_XE_DEVICE_QUERY){
  struct drm_xe_device_query *q=arg;
  if(q->query==DRM_XE_DEVICE_QUERY_ENGINES){
   if(!q->size){q->size=sizeof(struct drm_xe_query_engines)+sizeof(struct drm_xe_engine);return 0;}
   struct drm_xe_query_engines *e=(void *)(uintptr_t)q->data;e->num_engines=1;e->engines[0].instance.engine_class=DRM_XE_ENGINE_CLASS_RENDER;
  }else{
   assert(q->query==DRM_XE_DEVICE_QUERY_MEM_REGIONS);
   if(!q->size){q->size=sizeof(struct drm_xe_query_mem_regions)+sizeof(struct drm_xe_mem_region);return 0;}
   struct drm_xe_query_mem_regions *m=(void *)(uintptr_t)q->data;m->num_mem_regions=1;m->mem_regions[0].min_page_size=4096;
  }return 0;
 }
 if(cmd==DRM_IOCTL_XE_VM_CREATE){((struct drm_xe_vm_create *)arg)->vm_id=1;return 0;}
 if(cmd==DRM_IOCTL_XE_GEM_CREATE){struct drm_xe_gem_create *b=arg;assert(b->size==65536&&b->placement==1&&b->cpu_caching==DRM_XE_GEM_CPU_CACHING_WC);b->handle=2;return 0;}
 if(cmd==DRM_IOCTL_XE_GEM_MMAP_OFFSET)return 0;
 if(cmd==DRM_IOCTL_SYNCOBJ_CREATE){static uint32_t next=3;((struct drm_syncobj_create *)arg)->handle=next++;return 0;}
 if(cmd==DRM_IOCTL_XE_VM_BIND){struct drm_xe_vm_bind *b=arg;assert(b->bind.obj==2&&b->bind.addr==0x1000000&&b->bind.range==65536&&b->bind.pat_index==0);if(fail_bind){errno=EINVAL;return -1;}return 0;}
 if(cmd==DRM_IOCTL_SYNCOBJ_WAIT){struct drm_syncobj_wait *w=arg;struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);int64_t delta=w->timeout_nsec-(int64_t)t.tv_sec*1000000000-t.tv_nsec;assert(delta>0&&delta<=5000000000LL);return 0;}
 if(cmd==DRM_IOCTL_XE_EXEC_QUEUE_CREATE){struct drm_xe_exec_queue_create *q=arg;assert(q->width==1&&q->num_placements==1);q->exec_queue_id=6;return 0;}
 if(cmd==DRM_IOCTL_XE_EXEC){struct drm_xe_exec *e=arg;assert(e->address==0x1000000&&e->num_batch_buffer==1);uint32_t *b=mapping;assert(b[0]==0x10000002&&b[1]==0x1001000&&b[2]==0&&b[4]==0x05000000);*(uint32_t *)((char *)mapping+4096)=b[3];executions++;return 0;}
 if(cmd==DRM_IOCTL_MODE_GETRESOURCES){struct drm_mode_card_res *r=arg;if(r->connector_id_ptr){assert(!r->count_fbs&&!r->count_encoders);*(uint32_t *)(uintptr_t)r->connector_id_ptr=9;*(uint32_t *)(uintptr_t)r->crtc_id_ptr=7;}r->count_connectors=1;r->count_crtcs=1;r->count_encoders=1;return 0;}
 if(cmd==DRM_IOCTL_MODE_GETCONNECTOR){struct drm_mode_get_connector *c=arg;if(c->modes_ptr){assert(c->count_props==0);struct drm_mode_modeinfo *m=(void *)(uintptr_t)c->modes_ptr;m->hdisplay=128;m->vdisplay=72;m->type=DRM_MODE_TYPE_PREFERRED;*(uint32_t *)(uintptr_t)c->encoders_ptr=8;}c->connector_type=DRM_MODE_CONNECTOR_eDP;c->connection=1;c->count_modes=no_modes?0:1;c->count_encoders=1;c->count_props=4;return 0;}
 if(cmd==DRM_IOCTL_MODE_GETENCODER){((struct drm_mode_get_encoder *)arg)->crtc_id=7;return 0;}
 if(cmd==DRM_IOCTL_MODE_GETCRTC)return 0;
 if(cmd==DRM_IOCTL_MODE_CREATE_DUMB){struct drm_mode_create_dumb *b=arg;b->handle=11;b->pitch=b->width*4;b->size=b->pitch*b->height;return 0;}
 if(cmd==DRM_IOCTL_MODE_MAP_DUMB)return 0;
 if(cmd==DRM_IOCTL_MODE_ADDFB){struct drm_mode_fb_cmd *b=arg;assert(b->handle==11&&b->bpp==32&&b->depth==24);assert(((uint32_t *)mapping)[0]==0xff0000&&((uint32_t *)mapping)[127]==0x101010);b->fb_id=12;return 0;}
 if(cmd==DRM_IOCTL_MODE_SETCRTC){struct drm_mode_crtc *c=arg;if(c->mode_valid){assert(c->fb_id==12&&c->count_connectors==1);shows++;}else restores++;return 0;}
 if(cmd==DRM_IOCTL_XE_EXEC_QUEUE_DESTROY||cmd==DRM_IOCTL_GEM_CLOSE||cmd==DRM_IOCTL_SYNCOBJ_DESTROY||cmd==DRM_IOCTL_XE_VM_DESTROY||cmd==DRM_IOCTL_SET_MASTER||cmd==DRM_IOCTL_DROP_MASTER||cmd==DRM_IOCTL_MODE_RMFB||cmd==DRM_IOCTL_MODE_DESTROY_DUMB)return 0;
 fprintf(stderr,"Unexpected ioctl %lx\n",cmd);abort();
}
int main(void){
 puts("MOCK TEST ONLY - no GPU or screen emulation");
 assert(render(99)==0&&executions==1&&!mapping);
 fail_bind=1;assert(render(99)==1&&executions==1&&!mapping);
 assert(display(99)==0&&shows==1&&restores==1&&!mapping);
 no_modes=1;assert(display(99)==2&&shows==1&&!mapping);
 puts("PASS mocked submission, cleanup, KMS restore and absent-mode paths");return 0;
}
