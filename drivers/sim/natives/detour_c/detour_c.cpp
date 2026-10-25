// 官方 Detour (recastnavigation v1.6.0) 的薄 C 封装，供 natives/detour.py 用 ctypes 调用。
// 只做查询需要的最小面：建网格 + addTile、最近点、寻路(findPath+findStraightPath)、框查多边形、圆周多边形、多边形高度、多边形标志。
// 坐标一律是游戏世界坐标（网格偏移由 Python 侧处理）。dtPolyRef 为 32 位（未定义 DT_POLYREF64）。
#include <cstring>
#include "DetourNavMesh.h"
#include "DetourNavMeshQuery.h"
#include "DetourAlloc.h"
#include "DetourCommon.h"

#if defined(_WIN32)
#define DN_API extern "C" __declspec(dllexport)
#else
#define DN_API extern "C" __attribute__((visibility("default")))
#endif

static const int MAX_POLYS = 4096;

struct DN {
    dtNavMesh* mesh;
    dtNavMeshQuery* query;
    dtPolyRef polys[MAX_POLYS];
};

static void filt(dtQueryFilter& f, unsigned short incl, unsigned short excl) {
    f.setIncludeFlags(incl);
    f.setExcludeFlags(excl);
}

// status 输出 dtStatus；失败返回 NULL
DN_API void* dn_create(const float* orig, float tileW, float tileH, int maxTiles, int maxPolys, int maxNodes, unsigned int* status) {
    dtNavMeshParams p;
    memset(&p, 0, sizeof(p));
    dtVcopy(p.orig, orig);
    p.tileWidth = tileW;
    p.tileHeight = tileH;
    p.maxTiles = maxTiles;
    p.maxPolys = maxPolys;
    DN* h = new DN();
    h->mesh = dtAllocNavMesh();
    h->query = dtAllocNavMeshQuery();
    dtStatus s = h->mesh->init(&p);
    if (dtStatusSucceed(s)) s = h->query->init(h->mesh, maxNodes);
    if (status) *status = s;
    if (dtStatusFailed(s)) {
        dtFreeNavMeshQuery(h->query);
        dtFreeNavMesh(h->mesh);
        delete h;
        return 0;
    }
    return h;
}

DN_API void dn_destroy(void* hv) {
    DN* h = (DN*)hv;
    if (!h) return;
    dtFreeNavMeshQuery(h->query);
    dtFreeNavMesh(h->mesh);
    delete h;
}

// data 为标准 Detour tile 数据（'DNAV' 头起），内部复制一份交给网格管理
DN_API unsigned int dn_add_tile(void* hv, const unsigned char* data, int size) {
    DN* h = (DN*)hv;
    unsigned char* copy = (unsigned char*)dtAlloc(size, DT_ALLOC_PERM);
    if (!copy) return DT_FAILURE | DT_OUT_OF_MEMORY;
    memcpy(copy, data, size);
    dtStatus s = h->mesh->addTile(copy, size, DT_TILE_FREE_DATA, 0, 0);
    if (dtStatusFailed(s)) dtFree(copy);
    return s;
}

DN_API int dn_nearest(void* hv, const float* pos, const float* ext, unsigned short incl, unsigned short excl,
                      float* out, unsigned int* ref) {
    DN* h = (DN*)hv;
    dtQueryFilter f;
    filt(f, incl, excl);
    dtPolyRef r = 0;
    dtStatus s = h->query->findNearestPoly(pos, ext, &f, &r, out);
    if (ref) *ref = r;
    return (dtStatusSucceed(s) && r) ? 1 : 0;
}

// 返回拐点数（<=0 失败）；outPts 3*maxPts，outFlags 为各拐点所在多边形的标志，partial 置 1 表示终点不可达、路径止于最近处
DN_API int dn_path(void* hv, const float* sp, const float* ep, const float* ext, unsigned short incl, unsigned short excl,
                   float* outPts, unsigned short* outFlags, int maxPts, int* partial) {
    DN* h = (DN*)hv;
    dtQueryFilter f;
    filt(f, incl, excl);
    dtPolyRef sr = 0, er = 0;
    float s[3], e[3];
    if (partial) *partial = 0;
    if (dtStatusFailed(h->query->findNearestPoly(sp, ext, &f, &sr, s)) || !sr) return -1;
    if (dtStatusFailed(h->query->findNearestPoly(ep, ext, &f, &er, e)) || !er) return -2;
    int n = 0;
    dtStatus st = h->query->findPath(sr, er, s, e, &f, h->polys, &n, MAX_POLYS);
    if (dtStatusFailed(st) || n <= 0) return -3;
    float epos[3];
    dtVcopy(epos, e);
    if (h->polys[n - 1] != er) {
        if (partial) *partial = 1;
        h->query->closestPointOnPoly(h->polys[n - 1], e, epos, 0);
    }
    dtPolyRef* refs = (dtPolyRef*)dtAlloc(sizeof(dtPolyRef) * maxPts, DT_ALLOC_TEMP);
    unsigned char* sflags = (unsigned char*)dtAlloc(maxPts, DT_ALLOC_TEMP);
    int cnt = 0;
    st = h->query->findStraightPath(s, epos, h->polys, n, outPts, sflags, refs, &cnt, maxPts, 0);
    if (dtStatusSucceed(st) && outFlags) {
        for (int i = 0; i < cnt; ++i) {
            unsigned short pf = 0;
            if (refs[i]) h->mesh->getPolyFlags(refs[i], &pf);
            outFlags[i] = pf;
        }
    }
    dtFree(refs);
    dtFree(sflags);
    return dtStatusSucceed(st) ? cnt : -4;
}

DN_API int dn_query_box(void* hv, const float* center, const float* half, unsigned short incl, unsigned short excl,
                        unsigned int* refs, int maxRefs) {
    DN* h = (DN*)hv;
    dtQueryFilter f;
    filt(f, incl, excl);
    int n = 0;
    dtStatus s = h->query->queryPolygons(center, half, &f, (dtPolyRef*)refs, &n, maxRefs);
    return dtStatusSucceed(s) ? n : -1;
}

DN_API int dn_circle(void* hv, const float* center, float radius, const float* ext, unsigned short incl, unsigned short excl,
                     unsigned int* refs, int maxRefs) {
    DN* h = (DN*)hv;
    dtQueryFilter f;
    filt(f, incl, excl);
    dtPolyRef sr = 0;
    float c[3];
    if (dtStatusFailed(h->query->findNearestPoly(center, ext, &f, &sr, c)) || !sr) return -1;
    int n = 0;
    dtStatus s = h->query->findPolysAroundCircle(sr, c, radius, &f, (dtPolyRef*)refs, 0, 0, &n, maxRefs);
    return dtStatusSucceed(s) ? n : -1;
}

DN_API int dn_poly_height(void* hv, unsigned int ref, const float* pos, float* height) {
    DN* h = (DN*)hv;
    return dtStatusSucceed(h->query->getPolyHeight(ref, pos, height)) ? 1 : 0;
}

DN_API int dn_closest_on_poly(void* hv, unsigned int ref, const float* pos, float* out) {
    DN* h = (DN*)hv;
    return dtStatusSucceed(h->query->closestPointOnPoly(ref, pos, out, 0)) ? 1 : 0;
}

DN_API int dn_set_flags(void* hv, unsigned int ref, unsigned short flags) {
    return dtStatusSucceed(((DN*)hv)->mesh->setPolyFlags(ref, flags)) ? 1 : 0;
}

DN_API int dn_get_flags(void* hv, unsigned int ref, unsigned short* flags) {
    return dtStatusSucceed(((DN*)hv)->mesh->getPolyFlags(ref, flags)) ? 1 : 0;
}

DN_API int dn_tile_count(void* hv) {
    DN* h = (DN*)hv;
    const dtNavMesh* m = h->mesh;
    int n = 0;
    for (int i = 0; i < m->getMaxTiles(); ++i) {
        const dtMeshTile* t = m->getTile(i);
        if (t && t->header) ++n;
    }
    return n;
}
