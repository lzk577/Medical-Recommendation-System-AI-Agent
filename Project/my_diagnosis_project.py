import os
import asyncio
import logging
from termcolor import colored
from dotenv import load_dotenv

from aurite import Aurite
from aurite.config.config_models import AgentConfig, LLMConfig, ClientConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """
    启动Aurite，注册Infermedica诊断Agent并运行推理流程
    """
    load_dotenv()
    aurite = Aurite()

    try:
        await aurite.initialize()

        # 注册LLM
        llm_config = LLMConfig(
            llm_id="openai_gpt4_turbo",
            provider="openai",
            model_name="gpt-4-turbo"
        )
        await aurite.register_llm_config(llm_config)

        # 注册MCP服务器
        mcp_server_config = ClientConfig(
            name="diagnosis_server",
            server_path="diagnosis_server.py",
            capabilities=["tools"]
        )
        await aurite.register_client(mcp_server_config)

        # 注册Agent
        agent_config = AgentConfig(
            name="Diagnosis Agent",
            system_prompt=(
                "你是一名医学诊断助手。"
                "1) 首先调用 parse_text_to_evidence 将用户症状文本解析为结构化evidence;"
                "2) 然后调用 run_diagnosis 根据evidence预测可能疾病及概率;"
                "3) 最终用中文输出预测结果,最终输出结果按照可能的疾病概率降序排列。"
            ),
            mcp_servers=["diagnosis_server"],
            llm_config_id="openai_gpt4_turbo"
        )
        await aurite.register_agent(agent_config)

        # 用户输入症状文本
        ##user_query = "我最近一直发烧、头痛，并且伴随咳嗽和全身酸痛。"
        user_query = "我今年23岁，男性，我长期吸烟，最近感到胸痛乏力，并伴有咳嗽，有时还会咳血。我甚至还能摸到肿大的淋巴结"

        agent_result = await aurite.run_agent(
            agent_name="Diagnosis Agent",
            user_message=user_query
        )

        print(colored("\n--- Diagnosis Result ---", "yellow", attrs=["bold"]))
        print(colored(agent_result.primary_text, "cyan", attrs=["bold"]))

    except Exception as e:
        logger.error(f"Agent运行出错: {e}", exc_info=True)
        await aurite.shutdown()
        logger.info("Aurite 已安全关闭")

if __name__ == "__main__":
    asyncio.run(main())
