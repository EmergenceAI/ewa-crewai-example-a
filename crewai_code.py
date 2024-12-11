##Import necessary modules
__import__("pysqlite3")
import sys

sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

from crewai import Crew, Process, Task, Agent
from dotenv import load_dotenv
from crewai_tools import tool
import requests
import json
import os
import time

# Load environment variables
load_dotenv()

# Set OPENAI KEY AND MODEL from environment variables
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_MODEL_NAME"] = "gpt-4o"

# Set the environment variables for web automation
EMERGENCE_API_KEY = os.getenv("EMERGENCE_API_KEY")
URL = "https://api.emergence.ai/v0/orchestrators/em-web-automation/workflows"

# Define the workflow prompt for the usecase
USECASE = "What is the state of venture capital for AI in 2024? Provide a summary of the key trends and investments in the AI sector."


def get_api_response(
    base_url: str, method: str, headers: dict, payload: dict = {}
) -> dict:
    """
    Sends an HTTP request to a specified URL using the given method, headers, and payload.

    Parameters:
    - base_url (str): The URL for the API endpoint.
    - method (str): The HTTP method to use (e.g., 'GET' or 'POST').
    - headers (dict): The headers for the request.
    - payload (dict): The data to be sent with the request.

    Returns:
    - dict: The final response from the API in JSON format.
    """

    # Create a http request for the given API endpoint
    response = requests.request(method, base_url, headers=headers, json=payload)
    response = json.loads(response.text)

    return response


# Create the tool for the web automation
@tool("Web Automation tool")
def web_automation_tool(prompt: str) -> str:
    """A tool that can take a high-level natural language task as a prompt and break it down into multiple web navigation steps to accomplish the task, and perform those steps in a web browser. This tool can only do web navigation steps.

    Parameters:
    prompt (str): The  or prompt to guide the web navigation task.

    Returns:
    str: Relevant information retrieved from the web navigation results.

    """
    try:
        # Define the base URL for the API endpoint
        base_url = URL

        # Create the request payload with the  prompt
        payload = {
            "prompt": prompt,
        }

        # Set headers with content type and API key for authorization
        headers = {
            "Content-Type": "application/json",
            "apikey": EMERGENCE_API_KEY,
        }

        # Parse the response to extract the workflow ID for tracking status
        response = get_api_response(
            base_url=base_url, method="POST", headers=headers, payload=payload
        )
        workflowId = response["workflowId"]

        # Construct the URL to check the status of the workflow
        base_url = f"{URL}/{workflowId}"

        # Empty payload for the GET request to check status
        payload = {}

        # Set headers with content type and API key for authorization
        headers = {
            "apikey": EMERGENCE_API_KEY,
        }

        response = get_api_response(base_url=base_url, method="GET", headers=headers)

        print(response)

        # loop: Continue checking until the workflow status is "SUCCESS"
        while response["data"]["status"] in ["IN_PROGRESS", "QUEUED", "PLANNING"]:
            response = get_api_response(
                base_url=base_url, method="GET", headers=headers, payload=payload
            )
            time.sleep(10)

        # Check workflow status for the current workflow ID
        if (
            response["data"]["workflowId"] == workflowId
            and response["data"]["status"] == "SUCCESS"
        ):
            # Return the result if the workflow completes successfully
            return response["data"]["output"]["result"]

        # Return error message if the workflow does not complete successfully
        return "An error occurred while getting result of the prompt."
    except Exception as e:
        return f"An error occurred while performing the web automation: {str(e)}"


# Define an agent responsible for web automation tasks
web_automation_agent = Agent(
    role="An web automation agent to navigate web",
    goal="Get the relevant information from the web required for this prompt: {prompt}",
    verbose=True,
    memory=True,
    backstory=(
        "You are an expert in web automation. You can take a high-level natural language task as a prompt and break it down into multiple web navigation steps to accomplish the task, and perform those steps in a web browser. You could only do web navigation steps and nothing more."
    ),
    tools=[web_automation_tool],
    allow_delegation=True,
)


# Define a task for the web automation agent to execute
websearch_task = Task(
    description=(
        "For the provided prompt: {prompt}, do the web automation and get the relevant information."
    ),
    expected_output="Get the result of the provided prompt: {prompt}",
    tools=[web_automation_tool],
    agent=web_automation_agent,
)

# Define a Crew instance to manage agents and tasks, specifying workflow
crew = Crew(
    agents=[web_automation_agent],
    tasks=[websearch_task],
    process=Process.sequential,
    max_rpm=100,
    share_crew=True,
)

# Kick off the crew workflow by passing the input prompt
result = crew.kickoff(inputs={"prompt": USECASE})
