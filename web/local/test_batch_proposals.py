import unittest
from unittest.mock import patch
from batch_proposals import propose


class ProposalIsolationTests(unittest.TestCase):
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
