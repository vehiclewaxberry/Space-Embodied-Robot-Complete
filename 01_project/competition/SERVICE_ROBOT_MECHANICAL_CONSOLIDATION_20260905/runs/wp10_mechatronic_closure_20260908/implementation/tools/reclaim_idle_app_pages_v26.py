"""Owner-authorized memory recovery: trim idle resident pages, never close sessions.

Extends the verified handle-bound V24 routine to observed browser/AI app paths.
CPU/IO sampling, same-user/session, handle identity and ancestor exclusion remain.
"""
import sys
import memory_reclaim_safe_v24 as m
prior=m.role
def role(p,mode):
 r=prior(p,mode)
 if r or mode!='background':return r
 exe=m.norm(p.exe())
 if exe in ['c:/program files/google/chrome/application/chrome.exe',
 'c:/program files (x86)/microsoft/edge/application/msedge.exe',
 'c:/users/stude/.bun/install/global/node_modules/opencode-ai/bin/opencode.exe']:
  return 'trim_only_preserve_idle_application_session'
 if exe.startswith('c:/users/stude/appdata/roaming/claude/claude-code/') and exe.endswith('/claude.exe'):
  return 'trim_only_preserve_idle_cli_session'
 if exe.startswith('c:/program files/windowsapps/openai.codex_') and exe.endswith('/app/chatgpt.exe'):
  return 'trim_only_preserve_codex_UI_session'
m.role=role
if __name__=='__main__':m.run('background',sys.argv[1])
