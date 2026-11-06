"""Independent validator and provider-boundary checks; no paid API requests."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from pydantic import ValidationError
from pipeline_v2 import analyze,local_facts,validate,openai_facts,DocumentFacts,resolve_bundle

DOC='지역 공모전\n주최: 지역 문화원\n접수 마감: 2026년 11월 20일 18시 00분'


class EvidenceChecks(unittest.TestCase):
    def test_fabricated_date_quote_blocks_execution(self):
        facts=local_facts(DOC);facts.deadlines[0].quote='접수 마감: 2026년 12월 31일 18시 00분'
        result=validate(DOC,facts)
        self.assertIsNone(result['deadline']);self.assertTrue(result['review'])

    def test_fabricated_organizer_blocks_execution(self):
        facts=local_facts(DOC);facts.organizer.value='다른 기관'
        result=validate(DOC,facts)
        self.assertIsNone(result['identity']['organizer']);self.assertIsNone(result['deadline'])

    def test_no_year_is_not_filled(self):
        self.assertIsNone(analyze('공모전\n접수 마감: 11월 20일 18시')['deadline'])

    def test_quote_is_not_valid_when_action_evidence_is_absent(self):
        facts=local_facts(DOC);facts.action_quote='제출은 필수입니다'
        self.assertFalse(validate(DOC,facts)['action_required'])

    def test_model_cannot_override_explicit_opt_out(self):
        doc=DOC+'\n신청 불필요'
        facts=local_facts(DOC)
        result=validate(doc,facts)
        self.assertIsNone(result['deadline']);self.assertTrue(result['review'])

    def test_coupon_not_suppressed_by_application_opt_out(self):
        result=analyze('카페 쿠폰\n신청 불필요\n사용 기한: 2026년 11월 20일 18시 00분')
        self.assertEqual(result['deadline'],'2026-11-20T18:00:00+09:00')

    def test_invalid_calendar_date_needs_review(self):
        result=analyze('공모전\n접수 마감: 2026년 02월 30일 18시')
        self.assertIsNone(result['deadline']);self.assertTrue(result['review'])

    def test_time_on_third_line(self):
        result=analyze('공모전\n접수 마감:\n2026년 11월 20일\n오후 6시')
        self.assertEqual(result['deadline'],'2026-11-20T18:00:00+09:00')

    def test_date_range_not_silently_reduced_to_first_day(self):
        result=analyze('공모전\n접수 마감: 2026년 11월 01일 ~ 2026년 11월 20일 18시')
        self.assertIsNone(result['deadline']);self.assertTrue(result['review'])

    def test_same_name_different_event_day_is_separate(self):
        a=analyze(DOC+'\n행사일: 2026년 11월 23일')
        b=analyze(DOC+'\n행사일: 2026년 11월 24일')
        existing=[{'id':1,'identity':a['identity']}]
        self.assertIsNone(resolve_bundle(b,existing,'abc')[0])

    def test_ambiguous_name_is_reviewed_not_merged(self):
        a=analyze(DOC);b=analyze(DOC.replace('지역 문화원','다른 문화원'))
        c=analyze('지역 공모전\n접수 마감: 2026년 11월 20일 18시 00분')
        match,key=resolve_bundle(c,[{'id':1,'identity':a['identity']},{'id':2,'identity':b['identity']}],'abc')
        self.assertIsNone(match);self.assertIn('review',key);self.assertIsNone(c['deadline'])


class ProviderChecks(unittest.TestCase):
    def test_remote_permission_is_checked_before_network(self):
        with patch('openai.OpenAI') as factory:
            with self.assertRaises(ValueError):openai_facts(DOC,{'allow_external':False})
            factory.assert_not_called()

    def test_missing_key_stops_before_client_creation(self):
        with patch.dict(os.environ,{},clear=True),patch('openai.OpenAI') as factory:
            with self.assertRaisesRegex(ValueError,'OPENAI_API_KEY'):openai_facts(DOC,{'allow_external':True})
            factory.assert_not_called()

    def test_structured_schema_compatible_with_sdk(self):
        from openai.lib._pydantic import to_strict_json_schema
        schema=to_strict_json_schema(DocumentFacts)
        self.assertFalse(schema['additionalProperties'])
        self.assertIn('deadlines',schema['required'])
        self.assertNotIn('normalized',str(schema))

    def test_success_contract_and_usage_no_real_request(self):
        response=SimpleNamespace(status='completed',output_parsed=local_facts(DOC),
            usage=SimpleNamespace(model_dump=lambda:{'input_tokens':120,'output_tokens':90}),id='offline-fixture')
        client=Mock();client.responses.parse.return_value=response
        with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-test-not-a-real-key'}),patch('openai.OpenAI',return_value=client) as factory:
            facts,trace=openai_facts(DOC,{'allow_external':True,'model':'gpt-4.1-mini'})
            self.assertEqual(trace['usage']['input_tokens'],120)
            self.assertIsInstance(facts,DocumentFacts)
            self.assertEqual(factory.call_args.kwargs['max_retries'],0)
            self.assertFalse(client.responses.parse.call_args.kwargs['store'])
            self.assertNotIn('tools',client.responses.parse.call_args.kwargs)

    def test_incomplete_response_not_accepted(self):
        client=Mock();client.responses.parse.return_value=SimpleNamespace(status='incomplete',output_parsed=None)
        with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-test-not-a-real-key'}),patch('openai.OpenAI',return_value=client):
            with self.assertRaisesRegex(ValueError,'未완료|미완료'):openai_facts(DOC,{'allow_external':True})


if __name__=='__main__':unittest.main(verbosity=2)
