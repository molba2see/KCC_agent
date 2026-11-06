"""Interactive API evaluation; key stays in process memory, never in a file or browser."""
import getpass
import os
from compare_v2 import run

if __name__=='__main__':
    print('합성 텍스트 비교 실험: OpenAI API 최대 8회 호출. 현재 모델: '+os.environ.get('OPENAI_MODEL','gpt-4.1-mini'))
    if not os.environ.get('OPENAI_API_KEY'):
        os.environ['OPENAI_API_KEY']=getpass.getpass('OpenAI API key (표시·저장하지 않음): ').strip()
    run('openai')
