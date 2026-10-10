/* Same vector operations on native AVX512-VNNI and emulated AVX-VNNI. */
#include <immintrin.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef EMULATED_AVX
#define TARGET "avxvnni,avx2"
#define BUS256 _mm256_dpbusd_avx_epi32
#define BSS256 _mm256_dpbusds_avx_epi32
#define WSS256 _mm256_dpwssd_avx_epi32
#define WST256 _mm256_dpwssds_avx_epi32
#define BUS128 _mm_dpbusd_avx_epi32
#define BSS128 _mm_dpbusds_avx_epi32
#define WSS128 _mm_dpwssd_avx_epi32
#define WST128 _mm_dpwssds_avx_epi32
#else
#define TARGET "avx512vnni,avx512vl,avx2"
#define BUS256 _mm256_dpbusd_epi32
#define BSS256 _mm256_dpbusds_epi32
#define WSS256 _mm256_dpwssd_epi32
#define WST256 _mm256_dpwssds_epi32
#define BUS128 _mm_dpbusd_epi32
#define BSS128 _mm_dpbusds_epi32
#define WSS128 _mm_dpwssd_epi32
#define WST128 _mm_dpwssds_epi32
#endif
static uint64_t state=0x1234567890abcdeULL,hash=1469598103934665603ULL;
static uint64_t rnd(void){state^=state<<13;state^=state>>7;state^=state<<17;return state;}
static void absorb(void *p,unsigned n){unsigned char*s=p;for(unsigned i=0;i<n;i++){hash^=s[i];hash*=1099511628211ULL;}}
__attribute__((target(TARGET))) static void test(void){
 for(unsigned i=0;i<10000;i++){
  uint64_t a[4],b[4],c[4],out[4];
  for(unsigned j=0;j<4;j++){a[j]=rnd();b[j]=rnd();c[j]=rnd();}
  if(i<16){for(unsigned j=0;j<4;j++){a[j]=(i&1)?0x8000000080000000ULL:0x7fffffff7fffffffULL;b[j]=(i&2)?0x8000800080008000ULL:~0ULL;c[j]=(i&4)?0x8000800080008000ULL:~0ULL;}}
  __m256i x=_mm256_loadu_si256((void*)a),y=_mm256_loadu_si256((void*)b),z=_mm256_loadu_si256((void*)c);
#define V256(op,u,v,w) do{_mm256_storeu_si256((void*)out,op(u,v,w));absorb(out,32);}while(0)
  V256(BUS256,x,y,z);V256(BSS256,x,y,z);V256(WSS256,x,y,z);V256(WST256,x,y,z);
  V256(BUS256,x,x,x);V256(BSS256,x,x,x);V256(WSS256,x,x,x);V256(WST256,x,x,x);
  __m128i xx=_mm256_castsi256_si128(x),yy=_mm256_castsi256_si128(y),zz=_mm256_castsi256_si128(z);
#define V128(op) do{_mm_storeu_si128((void*)out,op(xx,yy,zz));absorb(out,16);}while(0)
  V128(BUS128);V128(BSS128);V128(WSS128);V128(WST128);
 }
}
int main(void){test();printf("VNNI native/emulated digest: %016llx\n",(unsigned long long)hash);return 0;}
