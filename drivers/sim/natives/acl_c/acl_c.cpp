// 官方 ACL v1.2.1（uniformly sampled）解码的薄 C 封装：RAWANIMA 里 HEAD[16]==1 的 DATA 块就是 ACL 1.2 CompressedClip。
#include <acl/core/compressed_clip.h>
#include <acl/algorithm/uniformly_sampled/decoder.h>
#include <cstdlib>
#include <cstring>

using namespace acl;

extern "C" {

// 返回 0 成功；hash_ok = 哈希校验是否通过（只报告，不拦）
__declspec(dllexport) int acl_info(const void* buf, int* num_bones, int* num_samples, float* sample_rate, int* has_scale, int* hash_ok)
{
	const CompressedClip* clip = static_cast<const CompressedClip*>(buf);
	if (clip->is_valid(false).any())
		return -1;
	const ClipHeader& h = get_clip_header(*clip);
	*num_bones = h.num_bones;
	*num_samples = static_cast<int>(h.num_samples);
	*sample_rate = h.sample_rate;
	*has_scale = h.has_scale;
	*hash_ok = clip->is_valid(true).empty() ? 1 : 0;
	return 0;
}

struct PoseWriter : OutputWriter
{
	float* out;  // 每骨骼 10 个 float：四元数 xyzw、位移 xyz、缩放 xyz
	void write_bone_rotation(uint16_t i, const Quat_32& q)
	{
		float* p = out + i * 10;
		p[0] = quat_get_x(q); p[1] = quat_get_y(q); p[2] = quat_get_z(q); p[3] = quat_get_w(q);
	}
	void write_bone_translation(uint16_t i, const Vector4_32& t)
	{
		float* p = out + i * 10 + 4;
		p[0] = vector_get_x(t); p[1] = vector_get_y(t); p[2] = vector_get_z(t);
	}
	void write_bone_scale(uint16_t i, const Vector4_32& s)
	{
		float* p = out + i * 10 + 7;
		p[0] = vector_get_x(s); p[1] = vector_get_y(s); p[2] = vector_get_z(s);
	}
};

// 在给定时刻（秒）解一帧完整姿势，out 至少 num_bones*10 个 float；rounding: 0=插值 1=向下取帧 2=向上 3=最近
__declspec(dllexport) int acl_sample(const void* buf, float t, int rounding, float* out)
{
	const CompressedClip* clip = static_cast<const CompressedClip*>(buf);
	if (clip->is_valid(false).any())
		return -1;
	uniformly_sampled::DecompressionContext<uniformly_sampled::DefaultDecompressionSettings> ctx;
	ctx.initialize(*clip);
	ctx.seek(t, static_cast<SampleRoundingPolicy>(rounding));
	PoseWriter w;
	w.out = out;
	ctx.decompress_pose(w);
	return 0;
}

}
