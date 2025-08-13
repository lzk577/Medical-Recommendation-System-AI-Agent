# location_project.py

import os
import asyncio
import logging
from termcolor import colored  # For colored print statements

from aurite import Aurite
# from aurite.config.config_models import AgentConfig, LLMConfig
from aurite.config.config_models import AgentConfig, LLMConfig, ClientConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_nearby_hospitals():
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
            name="my_location_server", # MCP server名称
            # This path is relative to your project root
            server_path="custom_mcp_servers/location_server.py", # MCP工具函数位置
            capabilities=["tools"],
        )
        await aurite.register_client(mcp_server_config) # 注册一个MCP server

        # 3. Define and register an Agent configuration
        agent_config = AgentConfig( # 定义agent
            name="Locate Agent",
            system_prompt="You are Locate Agent, an intelligent assistant specializing in locating people, places, and services based on user queries. " \
            "Your job is to accurately interpret the user's intent and provide the most relevant location-based responses using the available data. " \
            "If the user provide a specific address(Province, state or more precise address), use that information; otherwise, use the IP address. " \
            "Note that the address takes precedence over the IP. Give all the hospital results.",
            # Tell the agent to use our new server!
            mcp_servers=["my_location_server"], # agent能用哪些MCP server（server名称列表）
            llm_config_id="openai_gpt4_turbo", # agent用哪个大模型
        )
        await aurite.register_agent(agent_config)
        # --- End of Dynamic Registration Example ---

        # 4. Define the user's query for the agent.
        # user_query = "Where is me?"
        address ="downtown, LA, 90007"
        # address = "China Shandong Province Weifang City"
        # address = "Shanghai Pudong International Airport"
        client_ip = "221.204.112.100"
        user_query = f"What hospitals are nearby? My address is {address} and my IP is {client_ip}. Tell me which tools do you use and which ip I give you."
        agent_result = await aurite.run_agent( # 运行agent
            agent_name="Locate Agent", user_message=user_query # 指定哪个agent以及用户输入
        )

        # Print the agent's response in a colored format for better visibility.
        print(colored("\n--- Agent Result ---", "yellow", attrs=["bold"]))
        response_text = agent_result.primary_text

        # print(colored(f"Agent's response: {response_text}", "cyan", attrs=["bold"]))
        return response_text

    except Exception as e:
        logger.error(f"An error occurred during agent execution: {e}", exc_info=True)
        logger.info("Aurite shutdown complete.")
    
    finally:
        await aurite.shutdown() # 框架结束


# if __name__ == "__main__":
#     # Run the asynchronous main function.
#     asyncio.run(main())
