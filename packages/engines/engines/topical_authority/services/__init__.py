from __future__ import annotations
import hashlib, re
from typing import Any
from engines.topical_authority.models import EntityGraph, TopicEdge, TopicGraph, TopicNode, TopicalAuthorityReport
__all__ = ["TopicalAuthorityService"]
class TopicalAuthorityService:
    def analyze(self, site_id, *, site_context=None, options=None):
        if site_context is None: return TopicalAuthorityReport(site_id=site_id,tenant_id="")
        tenant_id=site_context.tenant_id
        eg=EntityGraph(); tg,cornerstone,sup_map=self._topic_graph(site_context)
        auth=self._authority_score(site_context,tg); cov=self._coverage_score(site_context,tg)
        return TopicalAuthorityReport(site_id=site_id,tenant_id=tenant_id,entity_graph=eg,topic_graph=tg,cornerstone_pages=cornerstone,supporting_page_map=sup_map,authority_score=auth,coverage_score=cov)
    def _topic_graph(self, ctx):
        kp_pages={}
        for p in ctx.pages:
            if p.focus_keyphrase: kp_pages.setdefault(p.focus_keyphrase,[]).append(p.page_id)
        nodes=[]; edges=[]; cornerstone=[]; sup_map={}
        for kp,pids in kp_pages.items():
            tid="topic_"+hashlib.sha256(kp.encode()).hexdigest()[:12]
            nodes.append(TopicNode(topic_id=tid,label=kp,pillar_page_id=pids[0] if pids else None,supporting_page_ids=pids[1:],coverage_score=min(1.0,len(pids)/max(1,5))))
            if pids: cornerstone.append(pids[0]); sup_map[pids[0]]=pids[1:]
        def tok(t): return frozenset(w for w in re.split(r"\W+",t.lower()) if len(w)>2)
        tm={n.topic_id:tok(n.label) for n in nodes}
        for i,a in enumerate(nodes):
            for b in nodes[i+1:]:
                ov=tm[a.topic_id]&tm[b.topic_id]
                if ov: edges.append(TopicEdge(from_topic_id=a.topic_id,to_topic_id=b.topic_id,weight=round(len(ov)/max(len(tm[a.topic_id]),1),2)))
        return TopicGraph(nodes=nodes,edges=edges),cornerstone,sup_map
    def _authority_score(self, ctx, tg):
        n=len(ctx.pages)
        if n==0: return 0.0
        cov=sum(nd.coverage_score for nd in tg.nodes)/max(1,len(tg.nodes)); ild=min(1.0,len(ctx.link_graph)/max(1,n*2))
        return round(cov*0.6+ild*0.4,4)
    def _coverage_score(self, ctx, tg):
        n=len(ctx.pages)
        if n==0: return 0.0
        return round(sum(1 for p in ctx.pages if p.focus_keyphrase)/n,4)
