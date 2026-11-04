from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
code = '''from core.spellcheck.service import Spellchecker
import sys
s = Spellchecker('build/dict-check','assets/dictionaries')
assert s.check(sys.argv[2],sys.argv[1])
assert not s.check('фжшґфжшґ' if sys.argv[1] == 'uk' else 'xyzqzzqxxx',sys.argv[1])
print(sys.argv[1],'OK',flush=True)
'''
words = dict(pl='fotografia',en='subtitle',de='Wörterbuch',fr='bonjour',es='palabra',it='buongiorno',uk='Україна')
for language,word in words.items():
    subprocess.run([sys.executable,'-c',code,language,word],cwd=root,check=True)
