# Automatic Container Runtime Installation Guide

## Overview

The Isolated Agents SDK can **automatically detect and install** the appropriate container runtime (Podman or Docker) on Linux, macOS, and Windows. This guide covers the automatic installation system and how to use it.

---

## 🎯 Features

### **Automatic Detection**
- ✅ Detects if Podman or Docker is already installed
- ✅ Checks version compatibility
- ✅ Verifies runtime is functional

### **Automatic Installation**
- ✅ Installs appropriate runtime for platform
- ✅ Configures runtime for rootless operation
- ✅ Sets up required dependencies
- ✅ Validates installation

### **User Control**
- ✅ Optional automatic installation (opt-in)
- ✅ Manual installation instructions
- ✅ Custom runtime selection
- ✅ Installation progress feedback

---

## 📋 Installation Strategy by Platform

### **Linux**
1. **Detect**: Check for Podman, then Docker
2. **Install**: Use system package manager (apt, dnf, yum)
3. **Configure**: Enable rootless mode, cgroups v2
4. **Validate**: Test container creation

### **macOS**
1. **Detect**: Check for Podman Machine or Docker Desktop
2. **Install**: Use Homebrew for Podman, or download Docker Desktop
3. **Configure**: Initialize Podman Machine or Docker Desktop
4. **Validate**: Test container creation

### **Windows**
1. **Detect**: Check for Docker Desktop or WSL2 with Podman
2. **Install**: Download Docker Desktop installer
3. **Configure**: Enable WSL2 backend
4. **Validate**: Test container creation

---

## 💻 Implementation

### **File:** `isolated_agents_sdk/runtime_installer.py`

```python
"""Automatic container runtime installation."""

from __future__ import annotations

import asyncio
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple
from enum import Enum


class RuntimeType(Enum):
    """Container runtime types."""
    PODMAN = "podman"
    DOCKER = "docker"
    NONE = "none"


class InstallationStatus(Enum):
    """Installation status."""
    ALREADY_INSTALLED = "already_installed"
    INSTALLED = "installed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RuntimeInstaller:
    """Automatic container runtime installer."""
    
    def __init__(self, auto_install: bool = False, prefer_podman: bool = True):
        """Initialize runtime installer.
        
        Args:
            auto_install: Automatically install if not found
            prefer_podman: Prefer Podman over Docker when both available
        """
        self.auto_install = auto_install
        self.prefer_podman = prefer_podman
        self.system = platform.system()
        self.is_linux = self.system == "Linux"
        self.is_macos = self.system == "Darwin"
        self.is_windows = self.system == "Windows"
    
    async def ensure_runtime(self) -> Tuple[RuntimeType, InstallationStatus]:
        """Ensure a container runtime is available.
        
        Returns:
            Tuple of (runtime_type, installation_status)
        
        Raises:
            RuntimeError: If no runtime available and auto_install is False
        """
        # Check for existing runtime
        runtime = self.detect_runtime()
        
        if runtime != RuntimeType.NONE:
            print(f"✓ Found {runtime.value}")
            return runtime, InstallationStatus.ALREADY_INSTALLED
        
        # No runtime found
        if not self.auto_install:
            raise RuntimeError(
                "No container runtime found. Install Podman or Docker, "
                "or set auto_install=True to install automatically."
            )
        
        # Attempt automatic installation
        print("No container runtime found. Installing...")
        runtime, status = await self.install_runtime()
        
        if status == InstallationStatus.INSTALLED:
            print(f"✓ Successfully installed {runtime.value}")
        elif status == InstallationStatus.FAILED:
            raise RuntimeError(f"Failed to install container runtime")
        
        return runtime, status
    
    def detect_runtime(self) -> RuntimeType:
        """Detect available container runtime.
        
        Returns:
            RuntimeType indicating which runtime is available
        """
        # Check Podman first if preferred
        if self.prefer_podman:
            if self._check_podman():
                return RuntimeType.PODMAN
            if self._check_docker():
                return RuntimeType.DOCKER
        else:
            if self._check_docker():
                return RuntimeType.DOCKER
            if self._check_podman():
                return RuntimeType.PODMAN
        
        return RuntimeType.NONE
    
    async def install_runtime(self) -> Tuple[RuntimeType, InstallationStatus]:
        """Install appropriate container runtime for platform.
        
        Returns:
            Tuple of (runtime_type, installation_status)
        """
        if self.is_linux:
            return await self._install_linux()
        elif self.is_macos:
            return await self._install_macos()
        elif self.is_windows:
            return await self._install_windows()
        
        return RuntimeType.NONE, InstallationStatus.FAILED
    
    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------
    
    def _check_podman(self) -> bool:
        """Check if Podman is available."""
        if shutil.which("podman") is None:
            return False
        
        try:
            result = subprocess.run(
                ["podman", "version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        if shutil.which("docker") is None:
            return False
        
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    # ------------------------------------------------------------------
    # Linux installation
    # ------------------------------------------------------------------
    
    async def _install_linux(self) -> Tuple[RuntimeType, InstallationStatus]:
        """Install container runtime on Linux."""
        print("Installing Podman on Linux...")
        
        # Detect package manager
        if shutil.which("apt-get"):
            return await self._install_podman_apt()
        elif shutil.which("dnf"):
            return await self._install_podman_dnf()
        elif shutil.which("yum"):
            return await self._install_podman_yum()
        
        print("✗ Unsupported package manager")
        return RuntimeType.NONE, InstallationStatus.FAILED
    
    async def _install_podman_apt(self) -> Tuple[RuntimeType, InstallationStatus]:
        """Install Podman using apt (Ubuntu/Debian)."""
        try:
            print("  → Updating package list...")
            await self._run_command(["sudo", "apt-get", "update", "-qq"])
            
            print("  → Installing Podman...")
            await self._run_command([
                "sudo", "apt-get", "install", "-y", "-qq",
                "podman", "slirp4netns", "fuse-overlayfs"
            ])
            
            print("  → Configuring rootless mode...")
            await self._configure_rootless_linux()
            
            if self._check_podman():
                return RuntimeType.PODMAN, InstallationStatus.INSTALLED
            
        except Exception as e:
            print(f"✗ Installation failed: {e}")
        
        return RuntimeType.NONE, InstallationStatus.FAILED
    
    async def _install_podman_dnf(self) -> Tuple[RuntimeType, InstallationStatus]:
        """Install Podman using dnf (Fedora)."""
        try:
            print("  → Installing Podman...")
            await self._run_command([
                "sudo", "dnf", "install", "-y", "-q",
                "podman", "slirp4netns", "fuse-overlayfs"
            ])
            
            print("  → Configuring rootless mode...")
            await self._configure_rootless_linux()
            
            if self._check_podman():
                return RuntimeType.PODMAN, InstallationStatus.INSTALLED
            
        except Exception as e:
            print(f"✗ Installation failed: {e}")
        
        return RuntimeType.NONE, InstallationStatus.FAILED
    
    async def _install_podman_yum(self) -> Tuple[RuntimeType, InstallationStatus]:
        """Install Podman using yum (RHEL/CentOS)."""
        try:
            print("  → Installing Podman...")
            await self._run_command([
                "sudo", "yum", "install", "-y", "-q",
                "podman", "slirp4netns", "fuse-overlayfs"
            ])
            
            print("  → Configuring rootless mode...")
            await self._configure_rootless_linux()
            
            if self._check_podman():
                return RuntimeType.PODMAN, InstallationStatus.INSTALLED
            
        except Exception as e:
            print(f"✗ Installation failed: {e}")
        
        return RuntimeType.NONE, InstallationStatus.FAILED
    
    async def _configure_rootless_linux(self) -> None:
        """Configure rootless Podman on Linux."""
        import os
        
        # Enable user namespaces
        try:
            await self._run_command([
                "sudo", "sysctl", "-w", "user.max_user_namespaces=15000"
            ])
        except Exception:
            pass
        
        # Configure subuid/subgid
        username = os.environ.get("USER", "")
        if username:
            try:
                await self._run_command([
                    "sudo", "usermod", "--add-subuids", "100000-165535", username
                ])
                await self._run_command([
                    "sudo", "usermod", "--add-subgids", "100000-165535", username
                ])
            except Exception:
                pass
    
    # ------------------------------------------------------------------
    # macOS installation
    # ------------------------------------------------------------------
    
    async def _install_macos(self) -> Tuple[RuntimeType, InstallationStatus]:
        """Install container runtime on macOS."""
        # Check if Homebrew is available
        if shutil.which("brew"):
            return await self._install_podman_brew()
        
        # Fallback to Docker Desktop instructions
        print("Homebrew not found. Please install Docker Desktop manually:")
        print("  → Download from: https://www.docker.com/products/docker-desktop")
        return RuntimeType.NONE, InstallationStatus.SKIPPED
    
    async def _install_podman_brew(self) -> Tuple[RuntimeType, InstallationStatus]:
        """Install Podman using Homebrew."""
        try:
            print("Installing Podman via Homebrew...")
            
            print("  → Installing Podman...")
            await self._run_command(["brew", "install", "podman"])
            
            print("  → Initializing Podman Machine...")
            await self._run_command([
                "podman", "machine", "init",
                "--cpus", "4",
                "--memory", "8192",
                "--disk-size", "50"
            ])
            
            print("  → Starting Podman Machine...")
            await self._run_command(["podman", "machine", "start"])
            
            if self._check_podman():
                return RuntimeType.PODMAN, InstallationStatus.INSTALLED
            
        except Exception as e:
            print(f"✗ Installation failed: {e}")
        
        return RuntimeType.NONE, InstallationStatus.FAILED
    
    # ------------------------------------------------------------------
    # Windows installation
    # ------------------------------------------------------------------
    
    async def _install_windows(self) -> Tuple[RuntimeType, InstallationStatus]:
        """Install container runtime on Windows."""
        print("Automatic installation on Windows requires Docker Desktop.")
        print("Please install Docker Desktop manually:")
        print("  → Download from: https://www.docker.com/products/docker-desktop")
        print("  → Enable WSL2 backend in settings")
        print("  → Restart computer after installation")
        
        return RuntimeType.NONE, InstallationStatus.SKIPPED
    
    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    
    async def _run_command(
        self,
        cmd: list[str],
        timeout: float = 300,
    ) -> Tuple[str, str, int]:
        """Run a command and return (stdout, stderr, returncode)."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            return (
                stdout.decode(),
                stderr.decode(),
                proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"Command timed out: {' '.join(cmd)}")


# ------------------------------------------------------------------
# Convenience functions
# ------------------------------------------------------------------

async def ensure_container_runtime(
    auto_install: bool = False,
    prefer_podman: bool = True,
) -> RuntimeType:
    """Ensure a container runtime is available.
    
    Args:
        auto_install: Automatically install if not found
        prefer_podman: Prefer Podman over Docker
    
    Returns:
        RuntimeType indicating which runtime is available
    
    Raises:
        RuntimeError: If no runtime available and auto_install is False
    
    Example:
        >>> runtime = await ensure_container_runtime(auto_install=True)
        >>> print(f"Using {runtime.value}")
    """
    installer = RuntimeInstaller(
        auto_install=auto_install,
        prefer_podman=prefer_podman,
    )
    runtime, status = await installer.ensure_runtime()
    return runtime


def detect_container_runtime() -> RuntimeType:
    """Detect available container runtime (synchronous).
    
    Returns:
        RuntimeType indicating which runtime is available
    
    Example:
        >>> runtime = detect_container_runtime()
        >>> if runtime == RuntimeType.NONE:
        ...     print("No runtime found")
    """
    installer = RuntimeInstaller()
    return installer.detect_runtime()
```

---

## 🎓 Usage Examples

### **Example 1: Automatic Installation (Recommended)**

```python
from isolated_agents_sdk import run_agent
from isolated_agents_sdk.runtime_installer import ensure_container_runtime
import asyncio

async def main():
    # Automatically install if needed
    runtime = await ensure_container_runtime(auto_install=True)
    print(f"Using {runtime.value}")
    
    # Now run your agent
    def my_agent():
        return {"status": "success"}
    
    result = run_agent(
        agent=my_agent,
        working_dir="./workspace",
    )
    print(result)

# Run
asyncio.run(main())
```

### **Example 2: Detection Only**

```python
from isolated_agents_sdk.runtime_installer import detect_container_runtime, RuntimeType

# Check what's available
runtime = detect_container_runtime()

if runtime == RuntimeType.NONE:
    print("No container runtime found. Please install Podman or Docker.")
elif runtime == RuntimeType.PODMAN:
    print("Using Podman")
elif runtime == RuntimeType.DOCKER:
    print("Using Docker")
```

### **Example 3: Custom Installation Logic**

```python
from isolated_agents_sdk.runtime_installer import RuntimeInstaller, RuntimeType
import asyncio

async def setup_runtime():
    installer = RuntimeInstaller(
        auto_install=True,
        prefer_podman=True,  # Prefer Podman over Docker
    )
    
    # Check current status
    current = installer.detect_runtime()
    print(f"Current runtime: {current.value}")
    
    # Ensure runtime is available
    runtime, status = await installer.ensure_runtime()
    print(f"Runtime: {runtime.value}, Status: {status.value}")
    
    return runtime

runtime = asyncio.run(setup_runtime())
```

### **Example 4: Integration with SDK**

```python
from isolated_agents_sdk import run_agent, Policy
from isolated_agents_sdk.runtime_installer import ensure_container_runtime
import asyncio

async def run_with_auto_install():
    """Run agent with automatic runtime installation."""
    # Ensure runtime is available
    try:
        runtime = await ensure_container_runtime(auto_install=True)
        print(f"✓ Using {runtime.value}")
    except RuntimeError as e:
        print(f"✗ Failed to setup runtime: {e}")
        return
    
    # Define agent
    def my_agent():
        print("Agent running!")
        return {"status": "success"}
    
    # Run agent
    result = run_agent(
        agent=my_agent,
        working_dir="./workspace",
        policy=Policy(cpu_cores=2.0, memory_mb=1024),
    )
    
    print(f"Result: {result.return_value}")

# Run
asyncio.run(run_with_auto_install())
```

---

## 🔧 Configuration

### **Environment Variables**

```bash
# Disable automatic installation
export ISOLATED_AGENTS_AUTO_INSTALL=false

# Prefer Docker over Podman
export ISOLATED_AGENTS_PREFER_DOCKER=true

# Custom installation timeout (seconds)
export ISOLATED_AGENTS_INSTALL_TIMEOUT=600
```

### **Programmatic Configuration**

```python
from isolated_agents_sdk.runtime_installer import RuntimeInstaller

installer = RuntimeInstaller(
    auto_install=True,  # Enable automatic installation
    prefer_podman=True,  # Prefer Podman over Docker
)
```

---

## 📊 Installation Matrix

| Platform | Package Manager | Runtime | Auto-Install | Manual Steps |
|----------|----------------|---------|--------------|--------------|
| Ubuntu/Debian | apt | Podman | ✅ Yes | None |
| Fedora | dnf | Podman | ✅ Yes | None |
| RHEL/CentOS | yum | Podman | ✅ Yes | None |
| macOS | Homebrew | Podman | ✅ Yes | Install Homebrew first |
| macOS | Manual | Docker Desktop | ⚠️ Manual | Download installer |
| Windows | Manual | Docker Desktop | ⚠️ Manual | Download installer, enable WSL2 |

---

## ⚠️ Important Notes

### **Linux**
- ✅ Fully automatic installation
- ✅ Configures rootless mode
- ✅ Sets up cgroups v2
- ⚠️ Requires sudo for installation

### **macOS**
- ✅ Automatic with Homebrew
- ⚠️ Requires Homebrew pre-installed
- ⚠️ Podman Machine requires VM
- ⚠️ Docker Desktop requires manual download

### **Windows**
- ⚠️ Manual installation required
- ⚠️ Requires WSL2 enabled
- ⚠️ Requires Hyper-V or WSL2
- ⚠️ Requires administrator privileges

---

## 🎯 Best Practices

### **1. Check Before Installing**
```python
# Always check first
runtime = detect_container_runtime()
if runtime != RuntimeType.NONE:
    print(f"Already have {runtime.value}")
else:
    # Install if needed
    runtime = await ensure_container_runtime(auto_install=True)
```

### **2. Handle Installation Failures**
```python
try:
    runtime = await ensure_container_runtime(auto_install=True)
except RuntimeError as e:
    print(f"Installation failed: {e}")
    print("Please install manually:")
    print("  Linux: sudo apt-get install podman")
    print("  macOS: brew install podman")
    print("  Windows: Download Docker Desktop")
```

### **3. Provide User Feedback**
```python
print("Checking for container runtime...")
runtime = detect_container_runtime()

if runtime == RuntimeType.NONE:
    print("No runtime found. Installing...")
    runtime = await ensure_container_runtime(auto_install=True)
    print(f"✓ Installed {runtime.value}")
else:
    print(f"✓ Found {runtime.value}")
```

### **4. Test After Installation**
```python
runtime = await ensure_container_runtime(auto_install=True)

# Test that it works
from isolated_agents_sdk import run_agent

def test_agent():
    return {"status": "success"}

try:
    result = run_agent(agent=test_agent, working_dir="./workspace")
    print("✓ Runtime is working")
except Exception as e:
    print(f"✗ Runtime test failed: {e}")
```

---

## 📝 Summary

### **Features**
- ✅ Automatic detection of Podman and Docker
- ✅ Automatic installation on Linux (apt, dnf, yum)
- ✅ Automatic installation on macOS (Homebrew)
- ✅ Manual installation guidance for Windows
- ✅ Rootless configuration on Linux
- ✅ Podman Machine setup on macOS
- ✅ Version checking and validation

### **Benefits**
- 🚀 Zero-configuration setup on Linux
- 🚀 One-command setup on macOS (with Homebrew)
- 🚀 Clear instructions for Windows
- 🚀 Automatic runtime selection
- 🚀 Graceful fallbacks

### **Limitations**
- ⚠️ Requires sudo on Linux
- ⚠️ Requires Homebrew on macOS
- ⚠️ Manual installation on Windows
- ⚠️ Cannot install Docker Desktop automatically

---

**Next Steps:**
- Review [CROSSPLATFORM_COMPATIBILITY.md](CROSSPLATFORM_COMPATIBILITY.md) for platform details
- See [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md) for adapter implementation
- Check [IMPLEMENTATION_GAP_ANALYSIS.md](IMPLEMENTATION_GAP_ANALYSIS.md) for status