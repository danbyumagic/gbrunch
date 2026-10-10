/* Cross-check patched QEMU against real x86 GFNI hardware, not a duplicate oracle.
 * Build with gcc -O2 -static -o build/gfni-test tools/test_gfni.c.
 */
#include <immintrin.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint64_t state = 0xdecafbad12345678ULL;
static uint64_t random_word(void) {
    state ^= state << 13; state ^= state >> 7; state ^= state << 17; return state;
}
static uint64_t hash = 1469598103934665603ULL;
static void absorb(const void *p, unsigned n) {
    const unsigned char *s = p;
    for (unsigned i=0; i<n; i++) { hash ^= s[i]; hash *= 1099511628211ULL; }
}
__attribute__((target("gfni,avx2,vpclmulqdq")))
static void test(unsigned iterations) {
    for (unsigned i=0; i<iterations; i++) {
        uint64_t a[4], b[4], out[4];
        for (unsigned j=0; j<4; j++) { a[j]=random_word(); b[j]=random_word(); }
        __m256i x = _mm256_loadu_si256((const __m256i*)a);
        __m256i y = _mm256_loadu_si256((const __m256i*)b);
#define CHECK256(expr) do { _mm256_storeu_si256((__m256i*)out, (expr)); absorb(out,32); } while(0)
        CHECK256(_mm256_gf2p8mul_epi8(x,y));
        CHECK256(_mm256_clmulepi64_epi128(x,y,0x00));
        CHECK256(_mm256_clmulepi64_epi128(x,y,0x01));
        CHECK256(_mm256_clmulepi64_epi128(x,y,0x10));
        CHECK256(_mm256_clmulepi64_epi128(x,y,0x11));
        CHECK256(_mm256_clmulepi64_epi128(x,x,0x11));
        CHECK256(_mm256_gf2p8affine_epi64_epi8(x,y,0));
        CHECK256(_mm256_gf2p8affine_epi64_epi8(x,y,0x63));
        CHECK256(_mm256_gf2p8affine_epi64_epi8(x,y,0xff));
        CHECK256(_mm256_gf2p8affineinv_epi64_epi8(x,y,0));
        CHECK256(_mm256_gf2p8affineinv_epi64_epi8(x,y,0x63));
        CHECK256(_mm256_gf2p8mul_epi8(x,x));
        CHECK256(_mm256_gf2p8affine_epi64_epi8(x,x,0x80));
        __m128i lo = _mm256_castsi256_si128(x), ly = _mm256_castsi256_si128(y);
#define CHECK128(expr) do { _mm_storeu_si128((__m128i*)out, (expr)); absorb(out,16); } while(0)
        CHECK128(_mm_gf2p8mul_epi8(lo,ly));
        CHECK128(_mm_gf2p8affine_epi64_epi8(lo,ly,0x63));
        CHECK128(_mm_gf2p8affineinv_epi64_epi8(lo,ly,0xff));
        memset(a,0,sizeof a); x = _mm256_loadu_si256((const __m256i*)a);
        CHECK256(_mm256_gf2p8affineinv_epi64_epi8(x,y,0x63));
    }
}
int main(void) {
    test(10000);
    printf("GFNI native/emulated digest: %016llx\n", (unsigned long long)hash);
    return 0;
}
