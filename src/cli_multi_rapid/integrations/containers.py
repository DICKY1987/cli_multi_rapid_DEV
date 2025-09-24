"""Container system integrations (Docker)."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .process import ProcessResult, ProcessRunner

logger = logging.getLogger(__name__)


@dataclass
class ContainerVersion:
    """Version information for container tools."""

    version: str
    tool: str

    def __str__(self) -> str:
        return f"{self.tool} {self.version}"


class ContainersAdapter:
    """Adapter for container operations (Docker)."""

    def __init__(self, runner: ProcessRunner, config: Dict[str, Any]):
        """Initialize containers adapter.

        Args:
            runner: ProcessRunner instance
            config: Containers configuration with tool paths
        """
        self.runner = runner
        self.config = config
        self.docker_path = self._get_tool_path("docker")

    def _get_tool_path(self, tool_name: str) -> str:
        """Get tool path from configuration."""
        tool_config = self.config.get(tool_name)
        if tool_config and hasattr(tool_config, "path"):
            return tool_config.path
        return tool_name  # Fallback to tool name

    def version(self) -> ContainerVersion:
        """Get Docker version information."""
        result = self.runner.run(f'"{self.docker_path}" --version')
        if result.ok:
            version_str = result.stdout.strip()
            # Extract version number from "Docker version X.Y.Z"
            if "Docker version" in version_str:
                version_num = version_str.split("Docker version")[1].strip().split()[0]
            else:
                version_num = version_str
            return ContainerVersion(version=version_num, tool="docker")
        else:
            return ContainerVersion(version="unknown", tool="docker")

    def ps(self, all_containers: bool = False) -> ProcessResult:
        """List running containers.

        Args:
            all_containers: Include stopped containers

        Returns:
            ProcessResult with container list
        """
        cmd = f'"{self.docker_path}" ps'
        if all_containers:
            cmd += " -a"
        return self.runner.run(cmd)

    def images(self) -> ProcessResult:
        """List Docker images.

        Returns:
            ProcessResult with image list
        """
        return self.runner.run(f'"{self.docker_path}" images')

    def run(
        self,
        image: str,
        command: Optional[str] = None,
        detach: bool = False,
        remove: bool = True,
        ports: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        **kwargs,
    ) -> ProcessResult:
        """Run a Docker container.

        Args:
            image: Docker image to run
            command: Command to run in container
            detach: Run in background
            remove: Remove container when it stops
            ports: Port mappings (host:container)
            volumes: Volume mounts (host:container)
            env_vars: Environment variables
            name: Container name
            **kwargs: Additional docker run arguments

        Returns:
            ProcessResult from docker run
        """
        cmd_parts = [f'"{self.docker_path}"', "run"]

        if detach:
            cmd_parts.append("-d")
        if remove:
            cmd_parts.append("--rm")
        if name:
            cmd_parts.extend(["--name", name])

        # Add port mappings
        if ports:
            for host_port, container_port in ports.items():
                cmd_parts.extend(["-p", f"{host_port}:{container_port}"])

        # Add volume mounts
        if volumes:
            for host_path, container_path in volumes.items():
                cmd_parts.extend(["-v", f"{host_path}:{container_path}"])

        # Add environment variables
        if env_vars:
            for key, value in env_vars.items():
                cmd_parts.extend(["-e", f"{key}={value}"])

        # Add additional arguments
        for key, value in kwargs.items():
            if value is True:
                cmd_parts.append(f"--{key}")
            elif value is not False:
                cmd_parts.extend([f"--{key}", str(value)])

        cmd_parts.append(image)
        if command:
            cmd_parts.append(command)

        return self.runner.run(" ".join(cmd_parts))

    def stop(self, container: str) -> ProcessResult:
        """Stop a running container.

        Args:
            container: Container name or ID

        Returns:
            ProcessResult from docker stop
        """
        return self.runner.run(f'"{self.docker_path}" stop {container}')

    def remove(self, container: str, force: bool = False) -> ProcessResult:
        """Remove a container.

        Args:
            container: Container name or ID
            force: Force removal

        Returns:
            ProcessResult from docker rm
        """
        cmd = f'"{self.docker_path}" rm'
        if force:
            cmd += " -f"
        cmd += f" {container}"
        return self.runner.run(cmd)

    def pull(self, image: str) -> ProcessResult:
        """Pull a Docker image.

        Args:
            image: Image to pull

        Returns:
            ProcessResult from docker pull
        """
        return self.runner.run(f'"{self.docker_path}" pull {image}')

    def build(
        self,
        path: str = ".",
        tag: Optional[str] = None,
        dockerfile: Optional[str] = None,
        build_args: Optional[Dict[str, str]] = None,
    ) -> ProcessResult:
        """Build a Docker image.

        Args:
            path: Build context path
            tag: Image tag
            dockerfile: Dockerfile path
            build_args: Build arguments

        Returns:
            ProcessResult from docker build
        """
        cmd_parts = [f'"{self.docker_path}"', "build"]

        if tag:
            cmd_parts.extend(["-t", tag])
        if dockerfile:
            cmd_parts.extend(["-f", dockerfile])

        # Add build arguments
        if build_args:
            for key, value in build_args.items():
                cmd_parts.extend(["--build-arg", f"{key}={value}"])

        cmd_parts.append(path)
        return self.runner.run(" ".join(cmd_parts))

    def compose_up(
        self,
        compose_file: str = "docker-compose.yml",
        detach: bool = True,
        cwd: Optional[str] = None,
    ) -> ProcessResult:
        """Run docker-compose up.

        Args:
            compose_file: Docker compose file path
            detach: Run in background
            cwd: Working directory

        Returns:
            ProcessResult from docker-compose up
        """
        cmd = f'"{self.docker_path}" compose -f {compose_file} up'
        if detach:
            cmd += " -d"
        return self.runner.run(cmd, cwd=cwd)

    def compose_down(
        self, compose_file: str = "docker-compose.yml", cwd: Optional[str] = None
    ) -> ProcessResult:
        """Run docker-compose down.

        Args:
            compose_file: Docker compose file path
            cwd: Working directory

        Returns:
            ProcessResult from docker-compose down
        """
        cmd = f'"{self.docker_path}" compose -f {compose_file} down'
        return self.runner.run(cmd, cwd=cwd)

    def logs(
        self, container: str, follow: bool = False, tail: Optional[int] = None
    ) -> ProcessResult:
        """Get container logs.

        Args:
            container: Container name or ID
            follow: Follow log output
            tail: Number of lines to show from end

        Returns:
            ProcessResult with container logs
        """
        cmd = f'"{self.docker_path}" logs'
        if follow:
            cmd += " -f"
        if tail:
            cmd += f" --tail {tail}"
        cmd += f" {container}"
        return self.runner.run(cmd)

    def exec(
        self, container: str, command: str, interactive: bool = True, tty: bool = True
    ) -> ProcessResult:
        """Execute command in running container.

        Args:
            container: Container name or ID
            command: Command to execute
            interactive: Keep STDIN open
            tty: Allocate a pseudo-TTY

        Returns:
            ProcessResult from docker exec
        """
        cmd = f'"{self.docker_path}" exec'
        if interactive:
            cmd += " -i"
        if tty:
            cmd += " -t"
        cmd += f" {container} {command}"
        return self.runner.run(cmd)


def create_containers_adapter(
    runner: ProcessRunner, config: Dict[str, Any]
) -> ContainersAdapter:
    """Create a containers adapter instance.

    Args:
        runner: ProcessRunner instance
        config: Containers configuration

    Returns:
        ContainersAdapter instance
    """
    return ContainersAdapter(runner, config)
