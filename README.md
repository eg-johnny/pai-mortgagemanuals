# PrismAI - Mortgage Manuals Assistant

AI-powered document assistant designed for Mortgage Manuals and Lending Policies.  
Built on the Entelligage Managed AI Platform, this solution allows users to interact with their specific compliance manuals and operational documents using secure, customized AI models.

---

## 🚀 Features

- 🔒 Private and secure AI interaction using Entelligage APIs.
- 📚 Query across mortgage policies, QC plans, and procedure manuals.
- 🏗️ Built with FastAPI and React for modular deployment.
- 🔧 Supports custom document ingestion and retrieval-augmented generation (RAG).
- ☁️ Azure-native infrastructure with isolated client environments.

---

## 🛠 Tech Stack

- **Backend:** FastAPI (Python)
- **Frontend:** React + Vite
- **Vector Search:** Azure AI Search
- **Memory Storage:** CosmosDB
- **Hosting:** Azure Container Apps

---

## 📥 Installation & Setup (Developer Local or Cloud)

### Step 1: Clone the repository

```bash
git clone https://github.com/eg-johnny/pai-mortgagemanuals.git
cd pai-mortgagemanuals
````

---

### ⚙️ Environment Configuration

#### Option A: Deploy with New Azure Resources (Recommended)

Copy and rename the environment template folder:

```bash
cp -r .azure/template-env .azure/new-env
```

Copy and rename the `.env-template` file inside your new environment folder:

```bash
cp .azure/new-env/.env-template .azure/new-env/.env
```

Edit the following files:

* `.azure/new-env/.env` ➡ Update environment variables for your deployment.
* `.azure/config.json` ➡ Update `defaultEnvironment` to `"new-env"`:

```json
{
  "version": 1,
  "defaultEnvironment": "new-env"
}
```

Login to Azure and deploy the environment:

```bash
azd login
azd up
```

This will:

* Provision all required Azure infrastructure (Container App, CosmosDB, Azure AI Search, etc.).
* Build and deploy your application into the Container App.

---

#### Option B: Use Existing Azure Resources (Advanced / BYO Cloud)

Prepare your existing Azure resources.

Reference them by setting the environment variables listed in:

* `./infra/main.parameters.json`

Set the variables using `azd env set`:

```bash
azd env set AZURE_SEARCH_ENDPOINT "<existing-endpoint>"
azd env set COSMOSDB_CONNECTION_STRING "<existing-connection>"
# Add other variables as needed
```

Deploy the application code:

```bash
azd up
```

> This method will **only deploy your app code**, skipping new resource provisioning.

---

## 💡 Notes

* Always ensure the correct `.env` and `config.json` are set before running `azd up`.
* Manage multiple environments by repeating the steps and using unique environment folder names.
* Review `./infra/main.parameters.json` for required and optional environment configurations.

---

## 💻 Usage

* Access the Assistant via the frontend UI.
* Query specific manuals, policies, or documents.
* Responses are filtered and validated against the client's custom knowledge base.

---

## 🤝 Contributing

Contributions are welcome!
Please open issues, feature requests, or submit PRs for enhancements.

---

## 📜 License

Proprietary.
©2025 Entelligage, Inc.
