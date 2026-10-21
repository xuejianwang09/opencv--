"""
10_mcp_add_server.py
MCP (Model Context Protocol) Server 示例
功能：提供 add 工具（两数相加）
基于官方 mcp Python SDK 2.x 的 MCPServer 实现

============================================================
  正确启动方式（自动打开浏览器）
============================================================
  fastmcp dev inspector 10_mcp_add_server.py:mcp
              ↑ 命令    ↑ 子命令         ↑ Python文件  ↑ server对象名

  说明：你的 mujoco 环境已装 fastmcp 4.0.0，这个命令会：
    1) 导入本文件，找到变量名 mcp（MCPServer 实例）
    2) 启动 MCP Inspector Web 服务
    3) 自动打开浏览器（一般 http://127.0.0.1:8090）
    4) 浏览器里 Tools → add → 填 a=2,b=3 → Run Tool 即可看到 result=5

============================================================
  其他启动方式
============================================================
  方式A - 直接跑（stdio 模式，会阻塞，不会开浏览器，必须由客户端连接）：
    python 10_mcp_add_server.py

  方式B - 用 npx inspector（需要 Node）：
    npx @modelcontextprotocol/inspector python 10_mcp_add_server.py

  方式C - 接入 IDE 客户端（Trae / Claude Desktop 的 MCP 配置）：
    见教程或文档

  端口冲突解决：加 --ui-port 8090 --server-port 8091
============================================================
"""
import sys

from mcp.server.mcpserver import MCPServer

# ===== 创建 MCP Server 实例 =====
# 参数 "MathServer" 是服务名，会展示给客户端
mcp = MCPServer("MathServer")


# ===== 注册工具：add =====
# 用 @mcp.tool() 装饰，SDK 根据函数签名 + 类型注解自动生成 JSON Schema
# 客户端（LLM）据此知道如何调用，参数名/类型/文档都会暴露给模型
@mcp.tool()
def add(a: int, b: int) -> int:
    """两个整数相加，返回它们的和。例如 add(2, 3) -> 5"""
    result = a + b
    # 注意：stdio 模式下 stdout 是 JSON-RPC 协议通道，调试信息只能走 stderr
    print(f"[server] add({a}, {b}) 实际执行 → 返回 {result}",
          file=sys.stderr, flush=True)
    return result


if __name__ == "__main__":
    # 以 stdio 传输启动 server：
    # 通过标准输入/输出与客户端通信，进程启动后阻塞，等待客户端发来工具调用请求
    # stdout 是 JSON-RPC 协议通道，启动信息只能走 stderr 才不会破坏协议
    print("[server] MathServer 启动 (stdio 模式，等待客户端连接...)",
          file=sys.stderr, flush=True)
    mcp.run()
