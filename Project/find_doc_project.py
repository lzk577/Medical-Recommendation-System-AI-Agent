# location_project.py

import os
import asyncio
import logging
from typing import Optional
from termcolor import colored  # For colored print statements

from aurite import Aurite
# from aurite.config.config_models import AgentConfig, LLMConfig
from aurite.config.config_models import AgentConfig, LLMConfig, ClientConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_doctor(hospitals: Optional[str] = None, symptoms: Optional[str] = None):

# async def main():
    """
    A simple example demonstrating how to initialize Aurite, run an agent,
    and print its response.
    """
    # Initialize the main Aurite application object.
    # This will load configurations based on `aurite_config.json` or environment variables.
    # Load environment variables from a .env file if it exists
    from dotenv import load_dotenv

    load_dotenv()

    aurite = Aurite()

    try:
        await aurite.initialize()

        # --- Dynamic Registration Example ---
        # The following section demonstrates how to dynamically register components
        # with Aurite. This is useful for adding or modifying configurations at
        # runtime without changing the project's JSON/YAML files.

        # 1. Define and register an LLM configuration
        llm_config = LLMConfig(
            llm_id="openai_gpt4_turbo",
            provider="openai",
            model_name="gpt-4-turbo",
        )
        await aurite.register_llm_config(llm_config)

        # 2. Define and register an MCP server configuration
        mcp_server_config = ClientConfig(
            name="doctor_server", # MCP server名称
            # This path is relative to your project root
            server_path="find_doctor_server.py", # MCP工具函数位置
            capabilities=["tools"],
        )
        await aurite.register_client(mcp_server_config) # 注册一个MCP server

        # 3. Define and register an Agent configuration
        agent_config = AgentConfig( # 定义agent
            name="Doctor Agent",
            system_prompt="You are an agent that uses a hospital list and a disease list to match entries in a CSV file and take the intersection.",
            mcp_servers=["doctor_server"], # agent能用哪些MCP server（server名称列表）
            llm_config_id="openai_gpt4_turbo", # agent用哪个大模型
        )
        await aurite.register_agent(agent_config)
        # --- End of Dynamic Registration Example ---

        # 4. Define the user's query for the agent.
        # hospitals = "Peachtree Orthopaedic Clinic, Hughston Clinic"
        # symptoms = "Orthopedic Hand Surgery, Orthopedic Sports Medicine"
        user_query = f"What is recommended doctor? This is hospitals list {hospitals}, and this is symptoms list {symptoms}."
        agent_result = await aurite.run_agent( # 运行agent
            agent_name="Doctor Agent", user_message=user_query # 指定哪个agent以及用户输入
        )

        # Print the agent's response in a colored format for better visibility.
        print(colored("\n--- Agent Result ---", "yellow", attrs=["bold"]))
        response_text = agent_result.primary_text

        print(colored(f"Agent's response: {response_text}", "cyan", attrs=["bold"]))
        return response_text

    except Exception as e:
        logger.error(f"An error occurred during agent execution: {e}", exc_info=True)
        logger.info("Aurite shutdown complete.")    

    finally:
        await aurite.shutdown() # 框架结束 

# if __name__ == "__main__":
#     # Run the asynchronous main function.
#     asyncio.run(main())
