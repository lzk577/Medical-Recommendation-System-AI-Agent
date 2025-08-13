# my_doctor_recommendation_project.py

# import os
# import asyncio
# import logging
# from termcolor import colored
# from dotenv import load_dotenv

# from aurite import Aurite
# from aurite.config.config_models import AgentConfig, LLMConfig, ClientConfig

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)


# async def main():
#     """
#     启动Aurite，注册CMS医生推荐Agent并运行示例查询
#     """
#     load_dotenv()
#     aurite = Aurite()

#     try:
#         await aurite.initialize()

#         # 注册LLM配置
#         llm_config = LLMConfig(
#             llm_id="openai_gpt4_turbo",
#             provider="openai",
#             model_name="gpt-4-turbo"
#         )
#         await aurite.register_llm_config(llm_config)

#         # 注册MCP服务器
#         mcp_server_config = ClientConfig(
#             name="doctor_recommendation_server",
#             server_path="config/mcp_servers/doctor_recommendation_server.py",
#             capabilities=["tools"]
#         )
#         await aurite.register_client(mcp_server_config)

#         # 注册Agent
#         agent_config = AgentConfig(
#             name="Doctor Recommendation Agent",
#             system_prompt=(
#                 "你是医疗助手，根据用户输入的专科名称和地点，"
#                 "调用 doctor_recommendation_server 提供的工具，"
#                 "返回医生姓名、专科、机构、地址信息。"
#             ),
#             mcp_servers=["doctor_recommendation_server"],
#             llm_config_id="openai_gpt4_turbo"
#         )
#         await aurite.register_agent(agent_config)

#         # 示例用户输入
#         user_query = "Find surgery doctors in Los Angeles"

#         agent_result = await aurite.run_agent(
#             agent_name="Doctor Recommendation Agent",
#             user_message=user_query
#         )

#         print(colored("\n--- 医生推荐结果 ---", "yellow", attrs=["bold"]))
#         print(colored(agent_result.primary_text, "cyan", attrs=["bold"]))

#     except Exception as e:
#         logger.error(f"Agent运行出错: {e}", exc_info=True)
#         await aurite.shutdown()
#         logger.info("Aurite 已安全关闭")


# if __name__ == "__main__":
#     asyncio.run(main())

# my_doctor_recommendation_project.py

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
    load_dotenv()
    aurite = Aurite()

    try:
        # 初始化 Aurite 环境
        await aurite.initialize()

        # 1️⃣ 注册 LLM
        llm_config = LLMConfig(
            llm_id="GPT4_OpenAI",
            provider="openai",
            model_name="gpt-4-turbo"
        )
        await aurite.register_llm_config(llm_config)

        # 2️⃣ 注册 MCP Server（新版 server）
        mcp_server_config = ClientConfig(
            name="doctor_recommendation_server",
            server_path="doctor_recommendation_server.py",
            capabilities=["tools"]
        )
        await aurite.register_client(mcp_server_config)

        # 3️⃣ 注册 Agent
        agent_config = AgentConfig(
            agent_id="DoctorRecommendationAgent",
            name="Doctor Recommendation Agent",
            system_prompt=(
                "你是医生推荐助手。当用户提供专科和地点信息后，"
                "请调用工具 `find_doctors`，并传入参数："
                "specialty（专科名称），location（城市或州），"
                "limit（结果数量，可选，默认50），"
                "offset（分页偏移，可选，默认0），"
                "filter_state（按州过滤，可选）。"
                "最后把工具返回的 total 和 doctors 列表，"
                "以易读的中文格式输出。"
            ),
            mcp_servers=["doctor_recommendation_server"],
            llm_config_id="GPT4_OpenAI"
        )
        await aurite.register_agent(agent_config)

        # 4️⃣ 与 Agent 交互：示例自然语言查询
        user_query = "Find surgery doctors in Los Angeles"

        result = await aurite.run_agent(
            agent_name="Doctor Recommendation Agent",
            user_message=user_query
        )

        print(colored("\n--- 医生推荐结果 ---", "yellow", attrs=["bold"]))
        print(colored(result.primary_text, "cyan", attrs=["bold"]))

    except Exception as e:
        logger.error(f"Agent运行出错: {e}", exc_info=True)
        await aurite.shutdown()
        logger.info("Aurite 已安全关闭")

if __name__ == "__main__":
    asyncio.run(main())
