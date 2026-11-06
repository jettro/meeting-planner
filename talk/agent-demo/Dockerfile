# The talk's terminal: uv, the four steps, and ttyd serving a shell on a web page
# (talk/design_agent_demo.md A4-A9). The key comes in at `docker run`, never here.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends make curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ttyd is not packaged for bookworm: its own release binary, pinned and checked.
ARG TARGETARCH
RUN case "$TARGETARCH" in \
      arm64) f=ttyd.aarch64 sum=b38acadd89d1d396a0f5649aa52c539edbad07f4bc7348b27b4f4b7219dd4165 ;; \
      amd64) f=ttyd.x86_64  sum=8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55 ;; \
      *) echo "no ttyd for $TARGETARCH" && exit 1 ;; \
    esac \
 && curl -fsSL -o /usr/local/bin/ttyd "https://github.com/tsl0922/ttyd/releases/download/1.7.7/$f" \
 && echo "$sum  /usr/local/bin/ttyd" | sha256sum -c - \
 && chmod +x /usr/local/bin/ttyd

WORKDIR /demo
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY Makefile *.py ./

ENV PYDANTIC_AI_NO_BANNER=1 \
    UV_NO_PROGRESS=1
# A short prompt: the room reads the command, not the path.
RUN echo 'PS1="\[\e[38;2;100;52;218m\]agent-demo\[\e[0m\] \$ "' >> /root/.bashrc

EXPOSE 7681
CMD ["ttyd", "--writable", "--port", "7681", \
     "-t", "fontSize=28", \
     "-t", "fontFamily=Menlo, monospace", \
     "-t", "theme={\"background\":\"#F8F5F5\",\"foreground\":\"#141418\",\"cursor\":\"#6434DA\",\"selectionBackground\":\"#EBA9FF\"}", \
     "bash"]
