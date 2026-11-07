import unittest
from unittest.mock import patch
from batch_proposals import propose


class ProposalIsolationTests(unittest.TestCase):
    def test_rejected_existing_folder_can_produce_a_truly_new_folder_name(self):
        files = [{'id': 'a', 'name': '제주여행_준비.txt', 'text': '제주여행 여행 항공권과 숙소 준비'}]
        catalog = [{'id': 'old', 'name': '여행', 'guide': '이전 여행 기록'}]
        responses = [{'project_id': 'new', 'purpose': '별도 주제입니다.'},
                     {'name': '여행', 'purpose': '여행 준비 자료입니다.'},
                     {'name': '제주여행 준비', 'purpose': '제주 여행 예약과 준비 자료입니다.'}]
        with patch('batch_proposals.model_json', side_effect=responses):
            groups = propose(None, None, files, catalog)
        self.assertEqual(groups[0]['project_id'], 'new')
        self.assertEqual(groups[0]['name'], '제주여행 준비')

    def test_invalid_folder_name_does_not_abort_other_groups(self):
        files = [{'id': 'a', 'name': '경제학.txt', 'text': '경제학 수요 공급'},
                 {'id': 'b', 'name': '제주여행.txt', 'text': '제주여행 항공권 숙소'}]
        invalid = {'name': '전혀없는주제', 'purpose': '잘못된 분류 이름'}
        valid = {'name': '제주여행', 'purpose': '제주 여행 준비 자료입니다.'}
        deferred, progress = [], []
        with patch('batch_proposals.model_json', side_effect=[invalid, invalid, invalid, valid]):
            groups = propose(None, None, files, [], deferred, lambda chosen, group: progress.append(len(group)))
        self.assertEqual(deferred, ['a'])
        self.assertEqual(groups[0]['files'], ['b'])
        self.assertEqual(sum(progress), 2)
