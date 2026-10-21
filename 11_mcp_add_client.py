"""
11_mcp_add_client.py
MCP Client 示例：以 stdio 方式连接到 10_mcp_add_server.py 并调用其 add 工具

============================================================
  启动方式（在 mujoco 环境里）
============================================================
    python 11_mcp_add_client.py                # 默认调用 add(2, 3)
    python 11_mcp_add_client.py --a 10 --b 25  # 自定义参数
    python 11_mcp_add_client.py --server 路径\\xx.py  # 指定别的 server

============================================================
  工作流程
============================================================
    1) 用 StdioServerParameters 配置子进程启动方式
       (command=sys.executable, args=[10_mcp_add_server.py])
    2) stdio_client 会 spawn 子进程，通过子进程的 stdin/stdout 通信
    3) ClientSession.initialize() 完成协议握手（交换版本/能力/服务名）
    4) session.list_tools() 拿到 server 暴露的工具清单
    5) session.call_tool("add", {"a":..., "b":...}) 实际调用并取结果

  关键点：本脚本既是 MCP server 的"父进程"，也是 MCP 客户端；
  server 进程由 stdio_client 在 with 退出时自动回收，无需手动 kill。
============================================================
"""
import argparse
import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


# 默认 server 脚本：与本文件同目录下的 10_mcp_add_server.py
SERVER_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "10_mcp_add_server.py",
)


async def run(a: int, b: int, server_path: str) -> None:
    # 1) 配置如何拉起 server 子进程
    #    command 用当前解释器(sys.executable)，保证用同一套依赖运行
    #    env=None 表示继承当前环境变量
    params = StdioServerParameters(
        command=sys.executable,
        args=[server_path],
        env=None,
    )

    # 2) stdio_client: spawn 子进程并建立读写流
    #    返回 (read_stream, write_stream) 二元组
    async with stdio_client(params) as (read, write):
        # 3) 在读写流之上建立 ClientSession
        async with ClientSession(read, write) as session:
            # 握手：交换 protocolVersion / capabilities / serverInfo
            init = await session.initialize()
            print("=" * 55)
            print("已连接到 MCP Server")
            print(f"  服务名     : {init.server_info.name}")
            print(f"  协议版本   : {init.protocol_version}")
            print(f"  能力       : {init.capabilities}")
            print("=" * 55)

            # 4) 列出工具：对应 server 里 @mcp.tool() 注册的函数
            tools = await session.list_tools()
            print("\n可用工具列表：")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")
                print(f"      input_schema: {t.input_schema}")

            # 5) 调用 add
            print("\n" + "=" * 55)
            print(f"调用 add(a={a}, b={b}) ...")
            result = await session.call_tool("add", {"a": a, "b": b})

            # result 是 CallToolResult（注意：字段名是 snake_case）：
            #   - .content: 返回内容块列表（通常是 TextContent）
            #   - .is_error: True 表示服务端执行报错
            print("返回内容：")
            if result.is_error:
                print("  [服务端报错]")
            for block in result.content:
                # TextContent 有 .text 字段
                text = getattr(block, "text", None)
                if text is not None:
                    print(f"  -> {text}")
                else:
                    print(f"  -> {block!r}")
            print("=" * 55)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MCP client：连接 10_mcp_add_server.py 并调用 add 工具",
    )
    parser.add_argument("--a", type=int, default=2, help="加数 a（默认 2）")
    parser.add_argument("--b", type=int, default=3, help="加数 b（默认 3）")
    parser.add_argument(
        "--server",
        type=str,
        default=SERVER_SCRIPT,
        help="MCP server 脚本路径（默认同目录 10_mcp_add_server.py）",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.server):
        print(f"找不到 server 脚本: {args.server}", file=sys.stderr)
        sys.exit(1)

    try:
        asyncio.run(run(args.a, args.b, args.server))
    except KeyboardInterrupt:
        print("\n已中断")


if __name__ == "__main__":
    main()
