# API Communication Flow

The interaction between the user, the frontend, and the backend follows a clear, stateless pattern. Here is a step-by-step breakdown of a typical chat request:

1. **User Sends Message:** The user types a message into the Next.js frontend and clicks "Send."

2. **Frontend Sends Request:** The frontend constructs a JSON payload containing the user's token, the prompt, the selected AI model, and the current conversation ID. It then sends this payload to the POST /chat endpoint on the FastAPI backend.

3. **Backend Validates and Prepares:**
    - The backend receives the request and first validates the user's token against the PostgreSQL database.
    - It retrieves the full message history for the current conversation from the database.
    - If the "Use MCP" option is enabled, it asynchronously calls the MCP servers to get a list of available tools.

4. **Backend Calls AI Provider:** The backend forwards the user's prompt, the chat history, and the list of available tools to the selected AI provider (e.g., Google Gemini or OpenAI).

5. **AI Responds with Tool Call or Text:**
    - The AI model processes the request. If it decides to use a tool, the backend executes that tool's function by communicating with the appropriate MCP server and sends the result back to the AI.
    - Once the AI generates a final text response, it is sent back to the backend.

6. **Backend Logs and Responds:**
    - The backend logs the AI's final response in the PostgreSQL database, associating it with the current conversation.
    - It then sends the final answer back to the Next.js frontend in a JSON response.

7. **Frontend Displays Response:** The frontend receives the response and dynamically adds the new message from the assistant to the chat window for the user to see.

This entire process is stateless from the perspective of the backend API. All long-term conversation state is managed by the frontend and stored persistently in the database, allowing the application to be scaled horizontally by simply running more instances of the backend container.