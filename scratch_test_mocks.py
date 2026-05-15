import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter

async def test_mock_podman():
    adapter = PodmanAdapter()
    
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"output\n", b""))
    proc.wait = AsyncMock(return_value=0)
    proc.returncode = 0
    
    async def fake_exec(*args, **kwargs):
        print(f"Fake exec: {args}")
        return proc

    with patch("shutil.which", return_value="/usr/bin/podman"), \
         patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await adapter.initialize()
        print("Initialized")
        
        res = await adapter.exec_in_container("c1", ["ls"])
        print(f"Result: {res}")

if __name__ == "__main__":
    asyncio.run(test_mock_podman())
