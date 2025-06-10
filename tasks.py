from invoke.tasks import task


@task
def build_docker_mcp(c):
    c.run("docker build --pull --rm -f 'Dockerfile' -t 'magaya-mcp-handshake:latest' '.'")
