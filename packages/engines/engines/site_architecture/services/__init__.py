"""Site Architecture Engine service (4.2) - pure computation from SiteContext."""
from __future__ import annotations
import hashlib, re
from typing import Any
from engines.site_architecture.models import GraphEdge, GraphExport, GraphNode, HierarchyNode, SiteArchitectureReport, TopicCluster

__all__ = ["SiteArchitectureService"]
_DAMPING = 0.85
_ITERATIONS = 20

class SiteArchitectureService:
    def analyze(self, site_id, *, site_context=None, options=None):
        if site_context is None:
            return SiteArchitectureReport(site_id=site_id, tenant_id="")
        pages = list(site_context.pages)
        edges = list(site_context.link_graph)
        page_ids = {p.page_id for p in pages}
        scores = self._pagerank(page_ids, edges)
        hierarchy = self._build_hierarchy(pages, scores)
        clusters = self._build_clusters(pages, site_id)
        depth_map = {h.page_id: h.depth for h in hierarchy}
        graph = self._build_graph(pages, edges, scores, depth_map, clusters)
        structure_score = self._structure_score(pages, edges, scores, clusters)
        return SiteArchitectureReport(site_id=site_id, tenant_id=site_context.tenant_id,
            crawl_id=site_context.crawl_id, hierarchy=hierarchy, clusters=clusters,
            link_equity_scores=scores, structure_score=structure_score, graph_export=graph)

    def _pagerank(self, page_ids, edges):
        n = len(page_ids)
        if n == 0: return {}
        scores = {pid: 1.0/n for pid in page_ids}
        out = {pid: set() for pid in page_ids}
        inc = {pid: set() for pid in page_ids}
        for e in edges:
            if e.from_page_id in page_ids and e.to_page_id in page_ids:
                out[e.from_page_id].add(e.to_page_id)
                inc[e.to_page_id].add(e.from_page_id)
        for _ in range(_ITERATIONS):
            ns = {}
            for pid in page_ids:
                r = (1.0 - _DAMPING) / n
                for src in inc[pid]: r += _DAMPING * (scores[src] / max(1, len(out[src])))
                ns[pid] = r
            scores = ns
        mx = max(scores.values()) if scores else 1.0
        return {k: round(v/mx, 4) for k,v in scores.items()}

    def _build_hierarchy(self, pages, scores):
        from urllib.parse import urlsplit, urlunsplit
        def depth(url):
            path = urlsplit(url).path.strip("/")
            return len([s for s in path.split("/") if s]) if path else 0
        def parent(url):
            parts = urlsplit(url); path = parts.path.rstrip("/")
            if "/" not in path[1:]: return None
            return urlunsplit((parts.scheme, parts.netloc, path.rsplit("/",1)[0],"",""))
        nodes = [HierarchyNode(page_id=p.page_id, url=p.url, depth=depth(p.url), link_equity_score=scores.get(p.page_id,0.0)) for p in pages]
        url_to_id = {p.url.rstrip("/"): p.page_id for p in pages}
        for node in nodes:
            par = parent(node.url)
            if par:
                node.parent_page_id = url_to_id.get(par)
                if node.parent_page_id:
                    pn = next((n for n in nodes if n.page_id == node.parent_page_id), None)
                    if pn and node.page_id not in pn.children: pn.children.append(node.page_id)
        return sorted(nodes, key=lambda n: n.depth)

    def _build_clusters(self, pages, site_id):
        def tok(t): return frozenset(w for w in re.split(r"\W+", t.lower()) if len(w)>2)
        seeds = [p for p in pages if p.focus_keyphrase]
        clusters = []; assigned = set()
        for seed in seeds:
            cid = "cluster_" + hashlib.sha256(f"{site_id}:{seed.focus_keyphrase}".encode()).hexdigest()[:12]
            stok = tok(seed.focus_keyphrase); members = [seed.page_id]; assigned.add(seed.page_id)
            for p in pages:
                if p.page_id in assigned: continue
                if p.focus_keyphrase and tok(p.focus_keyphrase) & stok:
                    members.append(p.page_id); assigned.add(p.page_id)
            clusters.append(TopicCluster(cluster_id=cid, topic_label=seed.focus_keyphrase,
                pillar_page_id=seed.page_id, member_page_ids=members,
                strength=min(1.0, len(members)/max(1,len(pages)))))
        return clusters

    def _build_graph(self, pages, edges, scores, depth_map, clusters):
        pid_cluster = {pid: c.cluster_id for c in clusters for pid in c.member_page_ids}
        pids = {p.page_id for p in pages}
        nodes = [GraphNode(id=p.page_id, label=p.title or p.slug or p.page_id[:8],
            depth=depth_map.get(p.page_id,0), score=round(scores.get(p.page_id,0.0),4),
            cluster_id=pid_cluster.get(p.page_id)) for p in pages]
        gedges = [GraphEdge(source=e.from_page_id, target=e.to_page_id, anchor_text=e.anchor_text)
            for e in edges if e.from_page_id in pids and e.to_page_id in pids]
        return GraphExport(nodes=nodes, edges=gedges)

    def _structure_score(self, pages, edges, scores, clusters):
        n = len(pages)
        if n == 0: return 0.0
        ld = min(1.0, len(edges)/max(1, n*3))
        cc = min(1.0, sum(len(c.member_page_ids) for c in clusters)/n)
        from urllib.parse import urlsplit
        deep = sum(1 for p in pages if len([s for s in urlsplit(p.url).path.strip("/").split("/") if s])>5)
        ds = 1.0 - min(1.0, deep/n)
        return round(ld*0.4 + cc*0.4 + ds*0.2, 4)
