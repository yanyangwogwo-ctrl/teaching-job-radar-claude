"""Shortlist teaching posts first seen in the last N days from the radar feed (for the daily report task).

Usage: python3 -I radar_report.py JOBS_JSON [DAYS]
Prints source health, then candidate teaching posts in three tiers:
  A  radar subjects (philosophy, ethics, critical thinking, GE, AI literacy, AI ethics/humanities)
  B  other humanities / social sciences
  C  other teaching posts (listed briefly)
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))
TEACH = re.compile(r'\b(lecturer|lectureship|teaching|tutor|instructor|professor|teacher|educator|adjunct|'
                   r'programme leader|program leader|course leader|faculty member)\b|講師|導師|教師|教學|教授', re.I)
NOT_TEACH = re.compile(r'\b(research assistant|research associate|research officer|research fellow|postdoctoral|'
                       r'post-doctoral|technician|technical officer|clerk|executive officer|administrative|'
                       r'manager|officer|coordinator|secretary|assistant registrar)\b', re.I)
TIER_A = re.compile(r'philosoph|\bethic|moral|critical thinking|\blogic\b|general education|common core|'
                    r'liberal studies|citizenship|ai literacy|ai education|generative ai|digital humanit|'
                    r'artificial intelligence (and|&) (society|humanit|ethic)|哲學|倫理|批判思考|邏輯|通識|公民', re.I)
TIER_B = re.compile(r'humanit|social scien|sociolog|politic|government|public policy|public administration|'
                    r'\bhistor|religio|theolog|cultur|anthropolog|gender|literat|linguist|global studies|'
                    r'asian studies|china studies|chinese studies|psycholog|criminolog|social work|'
                    r'社會|政治|歷史|宗教|文化|人文|社科|語言學|文學|心理', re.I)


def parse(stamp):
    return datetime.fromisoformat(stamp.replace('Z', '+00:00')) if stamp else None


def main():
    path, days = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 7
    feed = json.load(open(path, encoding='utf-8'))
    now = datetime.now(timezone.utc)
    since, day_ago = now - timedelta(days=days), now - timedelta(hours=30)
    print('GENERATED', feed['meta'].get('generated_at'), 'NOW', now.astimezone(HKT).strftime('%Y-%m-%d %H:%M HKT'))
    for source in sorted(feed['sources'], key=lambda s: s['id']):
        if source.get('status') != 'ok':
            print('SOURCE', source['id'], source.get('institution'), source.get('status'), source.get('severity'),
                  '| list', source.get('listing_complete'), '| detail', source.get('detail_complete_count'), '/',
                  source.get('detail_total_count'), '|', ' / '.join(source.get('errors') or [])[:220])
    tiers = {'A': [], 'B': [], 'C': []}
    for job in feed['jobs']:
        first = parse(job.get('first_seen'))
        if job.get('status') not in (None, 'open') or not first or first < since:
            continue
        if job.get('deadline') and job['deadline'] < now.astimezone(HKT).strftime('%Y-%m-%d'):
            continue
        title, dept = job.get('title') or '', job.get('department') or ''
        teaching = job.get('role') in ('lecturer', 'tutor', 'instructor') or (TEACH.search(title) and not NOT_TEACH.search(title))
        if not teaching:
            continue
        head = ' '.join([title, dept, (job.get('description') or '')[:2500]])
        if job.get('subjects') or TIER_A.search(head):
            tier = 'A'
        elif TIER_B.search(' '.join([title, dept, (job.get('description') or '')[:1200]])):
            tier = 'B'
        else:
            tier = 'C'
        tiers[tier].append((job, first))
    for tier in 'ABC':
        print(f'\n=== TIER {tier}: {len(tiers[tier])}')
        for job, first in sorted(tiers[tier], key=lambda item: (-(item[0].get('score') or 0), item[0]['institution'])):
            fresh = 'NEW24H ' if first >= day_ago else ''
            print(f"{fresh}[{job['institution']}] {job['title']} | {job.get('department') or '-'} | {job.get('employment_type')} | "
                  f"截止 {job.get('deadline') or job.get('deadline_raw') or '-'} | 首見 {first.astimezone(HKT):%m-%d} | "
                  f"score {job.get('score')} {job.get('subjects') or ''} | detail {job.get('detail_complete')} | {job['url']}")
            if tier != 'C':
                hits = sorted({m.group(0).lower() for m in TIER_A.finditer(job.get('description') or '')} |
                              {m.group(0).lower() for m in TIER_B.finditer(job.get('description') or '')})
                print('      hits:', hits[:12])


if __name__ == '__main__':
    main()
