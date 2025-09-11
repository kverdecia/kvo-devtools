import os
import asyncio

from pydantic import BaseModel

from .package import Package


class PythonInvoke(BaseModel):
    package: Package

    async def list_tasks(self) -> list[str]:
        """Runs `uv run inv --list` in the package directory and returns a list of the available tasks.

        Returns:
            list[str]: A list of task names.
        """
        process = await asyncio.create_subprocess_exec(
            'uv', 'run', 'inv', '--list',
            cwd=self.package.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"Failed to list tasks: {stderr.decode().strip()}")
        return [line.split()[0] for line in stdout.decode().strip().split("\n") if line][1:]

    async def run_task(self, task_name: str, args: list[str] | None = None) -> None:
        """Runs a specific task in the package directory.

        Args:
            task_name (str): The name of the task to run.
            args (list[str]): The arguments to pass to the task.
        """
        env = dict(os.environ)
        env.pop('VIRTUAL_ENV')
        process = await asyncio.create_subprocess_exec(
            'uv', 'run', 'inv', task_name, *(args or []),
            cwd=self.package.path,
            env=env,
        )
        await process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"Failed to run task '{task_name}'.")
