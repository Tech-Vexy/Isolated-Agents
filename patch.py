import re
content = open('tests/property/test_session_properties.py', 'r', encoding='utf-8').read()
repl = '''        fake_container_id = \
abc123fakeid\
        
        async def mock_exec(*args, **kwargs):
            mock_proc = unittest.mock.AsyncMock()
            mock_proc.returncode = 0
            mock_proc.wait = unittest.mock.AsyncMock(return_value=0)
            mock_proc.stdout.read = unittest.mock.AsyncMock(side_effect=[fake_container_id.encode() + b\
\\n\, b\\])
            mock_proc.stderr.read = unittest.mock.AsyncMock(return_value=b\
\)
            return mock_proc

        with unittest.mock.patch(\
asyncio.create_subprocess_exec\, side_effect=mock_exec) as mock_run:'''

content = re.sub(r'        fake_container_id = \
abc123fakeid\.*?with unittest\.mock\.patch\(\subprocess\.run\, return_value=mock_result\) as mock_run:', repl, content, flags=re.DOTALL)

repl_func = '''    async def fake_subprocess_exec(cmd, *args, **kwargs):
        if cmd == \
podman\ and args and args[0] == \rm\ and args[1] == \-f\:
            destroyed_containers.append(args[2])
        mock_proc = unittest.mock.AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = unittest.mock.AsyncMock(return_value=0)
        mock_proc.stdout.read = unittest.mock.AsyncMock(return_value=b\
\)
        mock_proc.stderr.read = unittest.mock.AsyncMock(return_value=b\
\)
        return mock_proc

    with unittest.mock.patch(\
asyncio.create_subprocess_exec\, side_effect=fake_subprocess_exec) as mock_run:'''

content = re.sub(r'    def fake_subprocess_run\(cmd, \*\*kwargs\):.*?with unittest\.mock\.patch\(\
subprocess\.run\, side_effect=fake_subprocess_run\):', repl_func, content, flags=re.DOTALL)

open('tests/property/test_session_properties.py', 'w', encoding='utf-8').write(content)
