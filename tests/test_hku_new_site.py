"""HKU's recruitment site changed on 2026-11-20: cards on /jobs/search,
filtered to Fractional / Part-time and Hourly-paid without any `query=`."""
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from monitor.http import CrawlError
from monitor.model import record
from monitor.official import collect_official, hku_page_url, parse_hku_detail, parse_hku_list
from monitor.run import read_config

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {source['id']: source for source in read_config(ROOT)[0]}
HKU = SOURCES['hku']
PART, HOURLY = 'a8dfe5e6ea2dd00e085f603d73791c5b', 'cec6687bdfba952002d3eeba8babee99'


def card(reference, title, kinds=('Fractional / Part-time',), closing='Closing on: Dec 27 2026',
         department='School of Public Health (22400)'):
    slug = title.lower().replace(' ', '-')
    types = ''.join(f'<li class="job-component-icon-and-text job-component-employment-type"><i></i><span> {kind} </span></li>' for kind in kinds)
    closing_html = (f'<div class="job-component-list"><ul><li class="job-component-icon-and-text job-component-closing-on">'
                    f'<i></i><span> {closing} </span></li></ul></div>') if closing else ''
    return (f'<article class="col-12 job-search-results-card-col"><div class="card job-search-results-card"><div class="card-body">'
            f'<h3 class="card-title job-search-results-card-title"><a href="https://jobs.hku.hk/jobs/{slug}-hong-kong-central-western">{title}</a></h3>'
            f'<div class="job-component-details"><div class="job-component-list"><ul>'
            f'<li class="job-component-icon-and-text job-component-requisition-identifier"><i></i><span> {reference} </span></li></ul></div>'
            f'<div class="job-component-list"><ul><li class="job-component-icon-and-text job-component-department"><i></i><span> {department} </span></li></ul></div>'
            f'<div class="job-component-list"><ul>{types}</ul></div>{closing_html}</div></div></div></article>')


def page(cards, counts=(26, 12), more=False, checked=True):
    boxes = ''
    for index, (value, label, count) in enumerate(((PART, 'Fractional / Part-time', counts[0]), (HOURLY, 'Hourly-paid', counts[1]),
                                                    ('2392f4be606afc5329f7f7c507bf74a2', 'Full-time', 426))):
        mark = ' checked="checked"' if checked and value != '2392f4be606afc5329f7f7c507bf74a2' else ''
        boxes += (f'<input type="checkbox" name="employment_type_uids[]" id="filter_employment_type_3_0_{index}" value="{value}"{mark}>'
                  f'<label for="filter_employment_type_3_0_{index}">{label} ({count} items)</label>')
    pager = '<a rel="next" class="page-link" href="/jobs/search?page=2">2</a>' if more else ''
    return f'<form class="job-search-results-form">{boxes}</form><div class="results">{"".join(cards)}</div><nav>{pager}</nav>'


def detail(text='Part-time Lecturer in Philosophy (Ref: 537714) to teach undergraduate ethics. ' * 4,
           kinds=('Fractional / Part-time',), closing='Closing on: Nov 30 2026'):
    types = ''.join(f'<li class="job-component-icon-and-text job-component-employment-type"><span> {kind} </span></li>' for kind in kinds)
    closing_html = f'<li class="job-component-icon-and-text job-component-closing-on"><span> {closing} </span></li>' if closing else ''
    return f'<main><ul>{types}{closing_html}</ul><div class="job-description" id="job_description_x"><p>{text}</p></div></main>'


class FakeClient:
    def __init__(self, pages):
        self.pages, self.requested = pages, []

    def get(self, url):
        self.requested.append(url)
        return self.pages[url]


class HkuListTests(unittest.TestCase):
    def test_a_card_becomes_a_record_with_the_old_requisition_identity(self):
        jobs, more, counts = parse_hku_list(HKU, page([card('537714', 'Part-time Lecturer in Geography')]))
        job = jobs[0]
        self.assertEqual((job['reference'], job['title'], job['department']),
                         ('537714', 'Part-time Lecturer in Geography', 'School of Public Health (22400)'))
        self.assertEqual((job['deadline'], job['deadline_type']), ('2026-12-27', 'closing'))
        self.assertEqual(job['employment_type'], 'part-time')
        self.assertTrue(job['url'].startswith('https://jobs.hku.hk/jobs/'))
        self.assertFalse(job['detail_complete'])
        self.assertEqual((more, counts), (False, [26, 12]))
        # The same requisition number on the old PageUp site gives the same record.
        old = record(HKU, 'Part-time Lecturer in Geography', 'https://jobs.hku.hk/en/job/537714/parttime-lecturer', '537714')
        self.assertEqual(job['id'], old['id'])

    def test_work_types_shown_on_the_card_decide_the_employment_type(self):
        jobs, _, _ = parse_hku_list(HKU, page([card('537775', 'Lecturer (holding the functional title of Consulting Associate)', ('Hourly-paid',)),
                                                card('537873', 'Senior Research Assistant', ('Fractional / Part-time', 'Full-time')),
                                                card('537460', 'Research Assistant I', closing=None)]))
        self.assertEqual([job['employment_type'] for job in jobs], ['hourly', 'mixed', 'part-time'])
        self.assertIsNone(jobs[2]['deadline'])

    def test_a_page_where_the_filter_did_not_apply_stops_the_source(self):
        with self.assertRaises(CrawlError) as caught:
            parse_hku_list(HKU, page([card('537714', 'Part-time Lecturer')], checked=False))
        self.assertTrue(caught.exception.stop_source)
        with self.assertRaises(CrawlError) as caught:
            parse_hku_list(HKU, page([card('537961', 'Safety Assistant', ('Full-time',))]))
        self.assertTrue(caught.exception.stop_source)

    def test_a_card_without_its_identifier_is_a_layout_change(self):
        broken = card('537714', 'Part-time Lecturer').replace('job-component-requisition-identifier', 'job-component-something-else')
        with self.assertRaises(CrawlError):
            parse_hku_list(HKU, page([broken]))

    def test_page_urls_keep_the_filter_and_never_carry_a_query(self):
        self.assertNotIn('query=', HKU['url'])
        self.assertEqual(hku_page_url(HKU['url'], 1), HKU['url'])
        second = dict(parse_qsl(urlsplit(hku_page_url(HKU['url'] + '&query=&page=9', 2)).query, keep_blank_values=True))
        self.assertEqual(second.get('page'), '2')
        self.assertNotIn('query', second)
        values = [value for key, value in parse_qsl(urlsplit(hku_page_url(HKU['url'], 3)).query) if key == 'employment_type_uids[]']
        self.assertEqual(values, [PART, HOURLY])


class HkuCollectTests(unittest.TestCase):
    def test_every_page_is_read_and_the_union_is_checked_against_the_filter_counts(self):
        first = [card(str(537000 + n), f'Part-time Research Assistant {n}') for n in range(30)]
        second = [card('537714', 'Part-time Lecturer in Geography')]
        pages = {HKU['url']: page(first, counts=(26, 12), more=True), hku_page_url(HKU['url'], 2): page(second, counts=(26, 12))}
        client = FakeClient(pages)
        client.pages.update({html.split('href="')[1].split('"')[0]: detail() for html in first + second})
        batch = collect_official(HKU, client)
        self.assertTrue(batch.listing_complete)
        self.assertEqual(len(batch.jobs), 31)
        self.assertEqual(client.requested[:2], [HKU['url'], hku_page_url(HKU['url'], 2)])
        self.assertTrue(all(job['detail_complete'] for job in batch.jobs))
        self.assertFalse(batch.errors)

    def test_fewer_jobs_than_the_larger_filter_count_is_not_a_complete_list(self):
        cards = [card(str(537000 + n), f'Part-time Research Assistant {n}') for n in range(20)]
        client = FakeClient({HKU['url']: page(cards, counts=(26, 12))})
        client.pages.update({html.split('href="')[1].split('"')[0]: detail() for html in cards})
        batch = collect_official(HKU, client)
        self.assertFalse(batch.listing_complete)
        self.assertIn('HKU 清單數目未能核對', ' '.join(batch.errors))
        self.assertEqual(len(batch.jobs), 20)


class HkuDetailTests(unittest.TestCase):
    def test_the_description_and_work_types_fill_the_record(self):
        job = parse_hku_list(HKU, page([card('537714', 'Part-time Lecturer in Geography', closing=None)]))[0][0]
        parse_hku_detail(job, detail(kinds=('Fractional / Part-time', 'Hourly-paid')))
        self.assertTrue(job['detail_complete'])
        self.assertIn('undergraduate ethics', job['description'])
        self.assertEqual(job['match_text'], job['description'])
        self.assertEqual(job['employment_type'], 'part-time')
        self.assertEqual((job['deadline'], job['deadline_raw']), ('2026-11-30', 'Closing on: Nov 30 2026'))

    def test_a_page_without_the_description_block_is_a_layout_change(self):
        job = parse_hku_list(HKU, page([card('537714', 'Part-time Lecturer')]))[0][0]
        with self.assertRaises(CrawlError):
            parse_hku_detail(job, '<main><p>Kiosk mode</p></main>')


if __name__ == '__main__':
    unittest.main()
