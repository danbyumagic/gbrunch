// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * GBRUNCH camera probe: list libcamera cameras, stream the first one through the simple pipeline
 * (software ISP), and log frame metadata plus a small thumbnail to logcat (tag gbcam). It runs once
 * as an init service, so the result lands in the GBLOG live logcat without a shell on the device.
 *
 *   gbcam-probe [frames]          default 60 frames
 * Thumbnail: "gbcam_ppm" lines, base64 of a binary PPM (P6), 160x120 or less.
 */
#include <android/log.h>
#include <sys/mman.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include <libcamera/libcamera.h>

using namespace libcamera;

#define LOG(...) __android_log_print(ANDROID_LOG_INFO, "gbcam", __VA_ARGS__)

static std::mutex mtx;
static std::condition_variable cv;
static std::vector<Request *> done;

static void requestComplete(Request *request)
{
	std::lock_guard<std::mutex> lock(mtx);
	done.push_back(request);
	cv.notify_one();
}

static std::string base64(const std::vector<uint8_t> &in)
{
	static const char t[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
	std::string out;
	for (size_t i = 0; i < in.size(); i += 3) {
		uint32_t v = in[i] << 16 | (i + 1 < in.size() ? in[i + 1] << 8 : 0) | (i + 2 < in.size() ? in[i + 2] : 0);
		out += t[v >> 18 & 63];
		out += t[v >> 12 & 63];
		out += i + 1 < in.size() ? t[v >> 6 & 63] : '=';
		out += i + 2 < in.size() ? t[v & 63] : '=';
	}
	return out;
}

/* Byte offsets of R, G, B in one pixel of the packed RGB formats the software ISP produces. */
static bool rgbLayout(const PixelFormat &f, int &bpp, int &r, int &g, int &b)
{
	/* DRM fourcc names list components from the most significant byte; memory is little endian. */
	static const std::map<PixelFormat, std::array<int, 4>> m = {
		{ formats::RGB888, { 3, 2, 1, 0 } }, { formats::BGR888, { 3, 0, 1, 2 } },
		{ formats::XRGB8888, { 4, 2, 1, 0 } }, { formats::ARGB8888, { 4, 2, 1, 0 } },
		{ formats::XBGR8888, { 4, 0, 1, 2 } }, { formats::ABGR8888, { 4, 0, 1, 2 } },
	};
	auto it = m.find(f);
	if (it == m.end())
		return false;
	bpp = it->second[0];
	r = it->second[1];
	g = it->second[2];
	b = it->second[3];
	return true;
}

static void analyse(const StreamConfiguration &cfg, const FrameBuffer *fb, bool thumbnail)
{
	const FrameBuffer::Plane &plane = fb->planes()[0];
	/* Map the whole dmabuf: NV12's CbCr plane follows the luma plane. */
	off_t end = lseek(plane.fd.get(), 0, SEEK_END);
	size_t len = end > 0 ? static_cast<size_t>(end) : plane.offset + plane.length;
	void *map = mmap(nullptr, len, PROT_READ, MAP_SHARED, plane.fd.get(), 0);
	if (map == MAP_FAILED) {
		LOG("mmap failed: %s", strerror(errno));
		return;
	}
	const uint8_t *p = static_cast<const uint8_t *>(map) + plane.offset;
	if (cfg.pixelFormat == formats::NV12) {
		unsigned int w = cfg.size.width, h = cfg.size.height, stride = cfg.stride;
		const uint8_t *uv = p + stride * h;
		uint64_t sy = 0, su = 0, sv = 0;
		unsigned int n = 0;
		for (unsigned int y = 0; y < h; y += 8)
			for (unsigned int x = 0; x < w; x += 8, n++) {
				sy += p[y * stride + x];
				su += uv[(y / 2) * stride + (x & ~1u)];
				sv += uv[(y / 2) * stride + (x & ~1u) + 1];
			}
		LOG("frame mean Y=%.1f Cb=%.1f Cr=%.1f", double(sy) / n, double(su) / n, double(sv) / n);
		if (thumbnail) {
			unsigned int scale = std::max(1u, std::max((w + 159) / 160, (h + 119) / 120));
			unsigned int tw = w / scale, th = h / scale;
			char hdr[32];
			int hl = snprintf(hdr, sizeof(hdr), "P5\n%u %u\n255\n", tw, th);
			std::vector<uint8_t> pgm(hdr, hdr + hl);
			for (unsigned int y = 0; y < th; y++)
				for (unsigned int x = 0; x < tw; x++)
					pgm.push_back(p[y * scale * stride + x * scale]);
			std::string s64 = base64(pgm);
			LOG("gbcam_ppm begin %ux%u bytes=%zu", tw, th, pgm.size());
			for (size_t i = 0; i < s64.size(); i += 900)
				LOG("gbcam_ppm %s", s64.substr(i, 900).c_str());
			LOG("gbcam_ppm end");
		}
		munmap(map, len);
		return;
	}
	int bpp, ro, go, bo;
	if (!rgbLayout(cfg.pixelFormat, bpp, ro, go, bo)) {
		LOG("format %s not analysed", cfg.pixelFormat.toString().c_str());
		munmap(map, len);
		return;
	}
	unsigned w = cfg.size.width, h = cfg.size.height, stride = cfg.stride;
	uint64_t sum[3] = {};
	unsigned n = 0;
	for (unsigned y = 0; y < h; y += 8)
		for (unsigned x = 0; x < w; x += 8, n++) {
			const uint8_t *px = p + y * stride + x * bpp;
			sum[0] += px[ro];
			sum[1] += px[go];
			sum[2] += px[bo];
		}
	LOG("frame mean R=%.1f G=%.1f B=%.1f", double(sum[0]) / n, double(sum[1]) / n, double(sum[2]) / n);
	if (thumbnail) {
		unsigned scale = std::max(1u, std::max((w + 159) / 160, (h + 119) / 120));
		unsigned tw = w / scale, th = h / scale;
		char hdr[32];
		int hl = snprintf(hdr, sizeof(hdr), "P6\n%u %u\n255\n", tw, th);
		std::vector<uint8_t> ppm(hdr, hdr + hl);
		for (unsigned y = 0; y < th; y++)
			for (unsigned x = 0; x < tw; x++) {
				const uint8_t *px = p + y * scale * stride + x * scale * bpp;
				ppm.push_back(px[ro]);
				ppm.push_back(px[go]);
				ppm.push_back(px[bo]);
			}
		std::string s = base64(ppm);
		LOG("gbcam_ppm begin %ux%u bytes=%zu", tw, th, ppm.size());
		for (size_t i = 0; i < s.size(); i += 900)
			LOG("gbcam_ppm %s", s.substr(i, 900).c_str());
		LOG("gbcam_ppm end");
	}
	munmap(map, len);
}

static int runOne(std::shared_ptr<Camera> camera, int frames, Size size, PixelFormat format);

/* gbcam-probe [frames [WxH:nv12|xrgb ...]] */
int main(int argc, char **argv)
{
	int frames = argc > 1 ? atoi(argv[1]) : 60;
	LOG("GBCAM_PROBE start, frames=%d", frames);
	/* init's domain transition sets AT_SECURE, so libcamera ignores LIBCAMERA_LOG_* (secure_getenv). */
	logSetTarget(LoggingTargetSyslog);
	logSetLevel("*", "INFO");
	auto cm = std::make_unique<CameraManager>();
	int ret = cm->start();
	if (ret) {
		LOG("CameraManager start failed: %d", ret);
		return 1;
	}
	LOG("cameras: %zu", cm->cameras().size());
	for (const auto &c : cm->cameras()) {
		const ControlList &props = c->properties();
		auto model = props.get(properties::Model);
		auto loc = props.get(properties::Location);
		std::string m = model ? std::string(*model) : "?";
		LOG("camera id=%s model=%s location=%d", c->id().c_str(), m.c_str(), loc ? *loc : -1);
	}
	if (cm->cameras().empty()) {
		LOG("GBCAM_PROBE result=no-camera");
		return 2;
	}
	std::shared_ptr<Camera> camera = cm->cameras()[0];
	std::vector<std::pair<Size, PixelFormat>> runs;
	for (int i = 2; i < argc; i++) {
		unsigned int w = 0, h = 0;
		char f[8] = {};
		if (sscanf(argv[i], "%ux%u:%7s", &w, &h, f) == 3)
			runs.push_back({ Size(w, h), std::string(f) == "nv12" ? formats::NV12 : formats::XRGB8888 });
	}
	if (runs.empty())
		runs.push_back({ Size(1280, 720), formats::XRGB8888 });
	for (auto &[size, format] : runs) {
		LOG("GBCAM_PROBE run %s %s", size.toString().c_str(), format.toString().c_str());
		runOne(camera, frames, size, format);
	}
	camera.reset();
	cm->stop();
	return 0;
}

static int runOne(std::shared_ptr<Camera> camera, int frames, Size size, PixelFormat format)
{
	done.clear();
	if (camera->acquire()) {
		LOG("GBCAM_PROBE result=acquire-failed");
		return 3;
	}
	std::unique_ptr<CameraConfiguration> config = camera->generateConfiguration({ StreamRole::Viewfinder });
	StreamConfiguration &cfg = config->at(0);
	static bool listed = false;
	for (const PixelFormat &f : listed ? std::vector<PixelFormat>{} : cfg.formats().pixelformats())
		for (const Size &s : cfg.formats().sizes(f))
			LOG("offered %s %s", f.toString().c_str(), s.toString().c_str());
	listed = true;
	cfg.size = size;
	cfg.pixelFormat = format;
	CameraConfiguration::Status st = config->validate();
	LOG("config %s status=%d", cfg.toString().c_str(), int(st));
	if (st == CameraConfiguration::Invalid || camera->configure(config.get())) {
		LOG("GBCAM_PROBE result=configure-failed");
		camera->release();
		return 4;
	}
	LOG("configured %s stride=%u frameSize=%u", cfg.toString().c_str(), cfg.stride, cfg.frameSize);

	FrameBufferAllocator alloc(camera);
	Stream *stream = cfg.stream();
	if (alloc.allocate(stream) < 0) {
		LOG("GBCAM_PROBE result=alloc-failed");
		camera->release();
		return 5;
	}
	std::vector<std::unique_ptr<Request>> requests;
	for (const auto &buf : alloc.buffers(stream)) {
		std::unique_ptr<Request> r = camera->createRequest();
		r->addBuffer(stream, buf.get());
		requests.push_back(std::move(r));
	}
	camera->requestCompleted.connect(requestComplete);
	if (camera->start()) {
		LOG("GBCAM_PROBE result=start-failed");
		camera->release();
		return 6;
	}
	for (auto &r : requests)
		camera->queueRequest(r.get());

	int got = 0, errors = 0;
	auto t0 = std::chrono::steady_clock::now();
	while (got < frames) {
		std::unique_lock<std::mutex> lock(mtx);
		if (!cv.wait_for(lock, std::chrono::seconds(5), [] { return !done.empty(); })) {
			LOG("timeout after %d frames", got);
			break;
		}
		Request *r = done.front();
		done.erase(done.begin());
		lock.unlock();
		got++;
		const FrameBuffer *fb = r->buffers().begin()->second;
		const FrameMetadata &md = fb->metadata();
		if (r->status() != Request::RequestComplete || md.status != FrameMetadata::FrameSuccess)
			errors++;
		const ControlList &meta = r->metadata();
		auto exp = meta.get(controls::ExposureTime);
		auto gain = meta.get(controls::AnalogueGain);
		if (got <= 3 || got % 15 == 0 || got == frames) {
			LOG("frame %d seq=%u status=%d bytes=%u exposure=%d gain=%.2f", got, md.sequence, int(md.status),
			    md.planes().empty() ? 0 : md.planes()[0].bytesused, exp ? *exp : -1, gain ? *gain : -1.0);
			analyse(cfg, fb, got == frames);
		}
		r->reuse(Request::ReuseBuffers);
		camera->queueRequest(r);
	}
	double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
	LOG("GBCAM_PROBE result=%s frames=%d errors=%d fps=%.1f", got == frames && !errors ? "ok" : "partial", got,
	    errors, got / secs);
	camera->stop();
	camera->requestCompleted.disconnect(requestComplete);
	camera->release();
	return 0;
}
