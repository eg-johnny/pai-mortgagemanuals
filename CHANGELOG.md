---
Generated on: 2025-02-27 20:23:04

### Changes made:

- app/backend/approaches/prompts/chat_answer_question.prompty
- app/backend/chat_history/cosmosdb.py
- app/frontend/src/api/api.ts
- app/frontend/src/components/Example/Example.module.css
- app/frontend/src/components/Footer/Footer.module.css
- app/frontend/src/components/Footer/Footer.tsx
- app/frontend/src/components/HistoryItem/HistoryItem.module.css
- app/frontend/src/components/HistoryItem/HistoryItem.tsx
- app/frontend/src/components/HistoryPanel/HistoryPanel.tsx
- app/frontend/src/components/HistoryProviders/CosmosDB.ts
- app/frontend/src/components/HistoryProviders/IProvider.ts
- app/frontend/src/components/HistoryProviders/IndexedDB.ts
- app/frontend/src/components/HistoryProviders/None.ts
- app/frontend/src/locales/en/translation.json
- app/frontend/src/pages/chat/Chat.module.css
- app/frontend/src/pages/layout/Layout.module.css
- infra/main.bicep

### Detailed changes:

#### app/backend/approaches/prompts/chat_answer_question.prompty
diff --git a/app/backend/approaches/prompts/chat_answer_question.prompty b/app/backend/approaches/prompts/chat_answer_question.prompty
index 434701a..a3129c8 100644
--- a/app/backend/approaches/prompts/chat_answer_question.prompty
+++ b/app/backend/approaches/prompts/chat_answer_question.prompty
@@ -38,7 +38,8 @@ You are a highly intelligent and resourceful assistant designed to serve as a co
 5. **Direct Quotes**: If a clear and concise direct quote exists, start with it. If multiple policies apply or a quote is unclear, begin with a summary, followed by supporting quotes.
 7. **Summarization**: Summarize the response in a user-friendly way. When applicable, follow with supporting excerpts.
 8. **Clarity**: Ensure the response is clear, concise, and actionable, guiding the employee to understand and implement the provided guidance.
-9. **Acknowledgment of Gaps**: If no answer can be determined with the context, state this transparently.
+9. **Limit to Context**: Provide responses based solely on the information from the text sources provided.
+10. **Acknowledgment of Gaps**: If no answer can be determined with the context, state this transparently.
 
 ### Process
 
#### app/backend/chat_history/cosmosdb.py
diff --git a/app/backend/chat_history/cosmosdb.py b/app/backend/chat_history/cosmosdb.py
index fca1585..e52bb60 100644
--- a/app/backend/chat_history/cosmosdb.py
+++ b/app/backend/chat_history/cosmosdb.py
@@ -50,6 +50,7 @@ async def post_chat_history(auth_claims: Dict[str, Any]):
             "type": "session",
             "title": title,
             "timestamp": timestamp,
+            "isDeleted": 0,
         }
 
         message_pair_items = []
@@ -64,7 +65,7 @@ async def post_chat_history(auth_claims: Dict[str, Any]):
                     "type": "message_pair",
                     "question": message_pair[0],
                     "response": message_pair[1],
-                }
+                    "isDeleted": 0,                }
             )
 
         batch_operations = [("upsert", (session_item,))] + [
@@ -95,7 +96,7 @@ async def get_chat_history_sessions(auth_claims: Dict[str, Any]):
         continuation_token = request.args.get("continuation_token")
 
         res = container.query_items(
-            query="SELECT c.id, c.entra_oid, c.title, c.timestamp FROM c WHERE c.entra_oid = @entra_oid AND c.type = @type ORDER BY c.timestamp DESC",
+            query="SELECT c.id, c.entra_oid, c.title, c.timestamp FROM c WHERE c.isDeleted = 0 AND c.entra_oid = @entra_oid AND c.type = @type ORDER BY c.timestamp DESC",
             parameters=[dict(name="@entra_oid", value=entra_oid), dict(name="@type", value="session")],
             partition_key=[entra_oid],
             max_item_count=count,
@@ -145,7 +146,7 @@ async def get_chat_history_session(auth_claims: Dict[str, Any], session_id: str)
 
     try:
         res = container.query_items(
-            query="SELECT * FROM c WHERE c.session_id = @session_id AND c.type = @type",
+            query="SELECT * FROM c WHERE c.isDeleted = 0 AND c.session_id = @session_id AND c.type = @type",
             parameters=[dict(name="@session_id", value=session_id), dict(name="@type", value="message_pair")],
             partition_key=[entra_oid, session_id],
         )
@@ -189,19 +190,60 @@ async def delete_chat_history_session(auth_claims: Dict[str, Any], session_id: s
             parameters=[dict(name="@session_id", value=session_id)],
             partition_key=[entra_oid, session_id],
         )
-
-        ids_to_delete = []
+        
         async for page in res.by_page():
             async for item in page:
-                ids_to_delete.append(item["id"])
-
-        batch_operations = [("delete", (id,)) for id in ids_to_delete]
-        await container.execute_item_batch(batch_operations=batch_operations, partition_key=[entra_oid, session_id])
+                item_id = item["id"]
+                operations =[{ 'op': 'replace', 'path': '/isDeleted', 'value': 1 }]
+                await container.patch_item(item=item_id, partition_key=[entra_oid, session_id], patch_operations=operations)        
         return await make_response("", 204)
     except Exception as error:
         return error_response(error, f"/chat_history/sessions/{session_id}")
 
 
+@chat_history_cosmosdb_bp.put("/chat_history/sessions/<session_id>/title")
+@authenticated
+async def update_chat_history_session_title(auth_claims: Dict[str, Any], session_id: str):
+    if not current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED]:
+        return jsonify({"error": "Chat history not enabled"}), 400
+
+    container: ContainerProxy = current_app.config[CONFIG_COSMOS_HISTORY_CONTAINER]
+    if not container:
+        return jsonify({"error": "Chat history not enabled"}), 400
+
+    entra_oid = auth_claims.get("oid")
+    if not entra_oid:
+        return jsonify({"error": "User OID not found"}), 401
+
+    try:
+        request_json = await request.get_json()
+        new_title = request_json.get("title")
+        if not new_title:
+            return jsonify({"error": "Title is required"}), 400
+
+        res = container.query_items(
+            query="SELECT * FROM c WHERE c.session_id = @session_id AND c.type = @type",
+            parameters=[dict(name="@session_id", value=session_id), dict(name="@type", value="session")],
+            partition_key=[entra_oid, session_id],
+        )
+
+        session_item = None
+        async for page in res.by_page():
+            async for item in page:
+                session_item = item
+                break
+
+        if not session_item:
+            return jsonify({"error": "Session not found"}), 404
+
+        session_item["title"] = new_title
+        await container.upsert_item(session_item)
+
+        return jsonify({"message": "Title updated successfully"}), 200
+    except Exception as error:
+        return error_response(error, f"/chat_history/sessions/{session_id}/title")
+
+
 @chat_history_cosmosdb_bp.before_app_serving
 async def setup_clients():
     USE_CHAT_HISTORY_COSMOS = os.getenv("USE_CHAT_HISTORY_COSMOS", "").lower() == "true"
#### app/frontend/src/api/api.ts
diff --git a/app/frontend/src/api/api.ts b/app/frontend/src/api/api.ts
index df95f80..8e1c91f 100644
--- a/app/frontend/src/api/api.ts
+++ b/app/frontend/src/api/api.ts
@@ -189,3 +189,19 @@ export async function deleteChatHistoryApi(id: string, idToken: string): Promise
         throw new Error(`Deleting chat history failed: ${response.statusText}`);
     }
 }
+
+export async function updateChatHistoryTitleApi(id: string, title: string, idToken: string): Promise<any> {
+    const headers = await getHeaders(idToken);
+    const response = await fetch(`/chat_history/sessions/${id}/title`, {
+        method: "PUT",
+        headers: { ...headers, "Content-Type": "application/json" },
+        body: JSON.stringify({ title })
+    });
+
+    if (!response.ok) {
+        throw new Error(`Updating chat history title failed: ${response.statusText}`);
+    }
+
+    const dataResponse: any = await response.json();
+    return dataResponse;
+}
#### app/frontend/src/components/Example/Example.module.css
diff --git a/app/frontend/src/components/Example/Example.module.css b/app/frontend/src/components/Example/Example.module.css
index dab8aec..d383fae 100644
--- a/app/frontend/src/components/Example/Example.module.css
+++ b/app/frontend/src/components/Example/Example.module.css
@@ -28,10 +28,10 @@
 
 .exampleText {
     margin: 0;
-    font-size: 1.25rem;
+    font-size: 1.3rem;
     width: 25rem;
     padding: 1rem;
-    min-height: 4.5rem;
+    min-height: 85px;
 }
 
 .examplesNavList li {
@@ -54,7 +54,8 @@
 
     .example {
         margin-bottom: 0.3125rem;
-        padding: 1.25rem;
+        padding: 0.75rem;
+        min-height: 85px;
     }
 
     .examplesNavList li:nth-of-type(2),
@@ -63,10 +64,7 @@
     }
     .exampleText {
         font-size: 1.1rem;
-        font-weight: 600;
         width: 15.5rem;
         padding: 0;
-        color: rgb(75, 94, 196);
-        min-height: 2.25rem;
     }
 }
#### app/frontend/src/components/Footer/Footer.module.css
diff --git a/app/frontend/src/components/Footer/Footer.module.css b/app/frontend/src/components/Footer/Footer.module.css
index 3107f3b..172e833 100644
--- a/app/frontend/src/components/Footer/Footer.module.css
+++ b/app/frontend/src/components/Footer/Footer.module.css
@@ -7,6 +7,7 @@
     color: white; /* Set the text color to white */
     font-size: smaller;
     width: 100%;
+    margin: 0;
 }
 
 .logo {
@@ -15,21 +16,55 @@
 
 .footer .links {
     display: flex;
+    text-align: center;
     gap: 1rem; /* Space between links */
 }
 
-.footer .right-link {
+.footer .rightLink {
     margin-left: auto;
+    text-align: center;
+    color: white;
+}
+
+.smallRightLink {
+    display: none;
 }
 
 .stackedLinks {
     display: flex;
     flex-direction: column;
     gap: 0.5rem; /* Space between stacked links */
-    text-align: right;
+    text-align: center;
+}
+.copyRight {
+    margin-top: -1.5rem;
+}
+.smallCopyRight {
+    margin-top: -1.5rem;
+    display: none;
 }
 @media (max-width: 991px) {
+    .egLogo {
+        display: none;
+    }
     .footer {
+        justify-content: space-evenly;
+    }
+    .copyRight {
+        margin-top: 0rem;
+        display: none;
+    }
+    .smallCopyRight {
+        margin-top: 0rem;
+        display: block;
+    }
+    .footer .smallRightLink {
+        margin-left: auto;
+        text-align: center;
+        color: white;
+        display: flex;
+    }
+    .rightLink {
         display: none;
     }
 }
#### app/frontend/src/components/Footer/Footer.tsx
diff --git a/app/frontend/src/components/Footer/Footer.tsx b/app/frontend/src/components/Footer/Footer.tsx
index 3fc6e07..216d0a2 100644
--- a/app/frontend/src/components/Footer/Footer.tsx
+++ b/app/frontend/src/components/Footer/Footer.tsx
@@ -5,9 +5,16 @@ export const Footer = () => {
     const year = new Date().getFullYear();
     return (
         <footer className={styles.footer}>
-            <a href="https://entelligage.com/" target="_blank">
-                <img src="https://stjeegpqns5eeds.blob.core.windows.net/assets/EntelligageAI-Banner.png" alt="Logo" className={styles.logo} />
-            </a>
+            <div className={styles.stackedLinks}>
+                <a href="https://entelligage.com/" target="_blank" className={styles.egLogo}>
+                    <img src="https://stjeegpqns5eeds.blob.core.windows.net/assets/EntelligageAI-Banner.png" alt="Logo" className={styles.logo} />
+                </a>
+                <div className={styles.smallCopyRight}>
+                    &copy; {year} Entelligage Inc. <br />
+                    All Rights Reserved
+                </div>
+                <div className={styles.copyRight}>&copy; {year} Entelligage Inc. All Rights Reserved</div>
+            </div>
             <div className={styles.links}>
                 <a href="https://entelligage.com/privacy-policy" target="_blank" style={{ color: "white" }}>
                     Privacy Policy
@@ -22,14 +29,14 @@ export const Footer = () => {
                     Acceptable Use
                 </a>
             </div>
-            <div className={styles.stackedLinks}>
-                <a href="https://entelligage.com/" target="_blank" className={styles.rightLink} style={{ color: "white" }}>
-                    &copy; {year} Entelligage Inc., All Rights Reserved.
-                </a>
-                <a href="https://mortgagemanuals.com/" target="_blank" className={styles.rightLink} style={{ color: "white" }}>
-                    &copy; {year} Mortgage Manuals, All Rights Reserved.
-                </a>
-            </div>
+            <a href="https://mortgagemanuals.com/" target="_blank">
+                <div className={styles.smallRightLink}>
+                    &copy; {year} Mortgage Manuals
+                    <br />
+                    All Rights Reserved.
+                </div>
+                <div className={styles.rightLink}>&copy; {year} Mortgage Manuals, All Rights Reserved.</div>
+            </a>
         </footer>
     );
 };
#### app/frontend/src/components/HistoryItem/HistoryItem.module.css
diff --git a/app/frontend/src/components/HistoryItem/HistoryItem.module.css b/app/frontend/src/components/HistoryItem/HistoryItem.module.css
index 7424595..a35f617 100644
--- a/app/frontend/src/components/HistoryItem/HistoryItem.module.css
+++ b/app/frontend/src/components/HistoryItem/HistoryItem.module.css
@@ -11,6 +11,11 @@
     background-color: #f3f4f6;
 }
 
+.historyItem:hover .historyItemTitle {
+    text-decoration: underline;
+    color: blue;
+}
+
 .historyItemButton {
     flex-grow: 1;
     text-align: left;
@@ -25,7 +30,7 @@
     font-size: 1rem;
 }
 
-.deleteIcon {
+.editIcon .deleteIcon {
     width: 20px;
     height: 20px;
 }
@@ -41,12 +46,29 @@
     color: #6b7280;
 }
 
+.editButton {
+    opacity: 0;
+    transition: opacity 0.2s;
+    background: none;
+    border: none;
+    cursor: pointer;
+    padding: 4px;
+    border-radius: 9999px;
+    color: #6b7280;
+}
+
 .historyItem:hover .deleteButton,
 .deleteButton:focus {
     opacity: 1;
 }
 
-.deleteButton:hover {
+.historyItem:hover .editButton,
+.editButton:focus {
+    opacity: 1;
+}
+
+.deleteButton:hover,
+.editButton:hover {
     color: #111827;
 }
 
@@ -92,6 +114,7 @@
     gap: 16px;
 }
 
+.modalSubmitButton,
 .modalCancelButton,
 .modalConfirmButton {
     padding: 8px 16px;
@@ -111,6 +134,11 @@
     color: white;
 }
 
+.modalSubmitButton {
+    background-color: blue;
+    color: white;
+}
+
 .modalCancelButton:hover {
     background-color: #e5e7eb;
 }
@@ -118,3 +146,15 @@
 .modalConfirmButton:hover {
     background-color: #dc2626;
 }
+
+.modalSubmitButton:hover {
+    background-color: blue;
+}
+
+.modalInput {
+    width: 100%;
+    padding: 8px;
+    border-radius: 4px;
+    border: 1px solid #d1d5db;
+    margin-bottom: 16px;
+}
#### app/frontend/src/components/HistoryItem/HistoryItem.tsx
diff --git a/app/frontend/src/components/HistoryItem/HistoryItem.tsx b/app/frontend/src/components/HistoryItem/HistoryItem.tsx
index 5aca674..c975720 100644
--- a/app/frontend/src/components/HistoryItem/HistoryItem.tsx
+++ b/app/frontend/src/components/HistoryItem/HistoryItem.tsx
@@ -2,7 +2,7 @@ import { useState, useCallback } from "react";
 import { useTranslation } from "react-i18next";
 import styles from "./HistoryItem.module.css";
 import { DefaultButton } from "@fluentui/react";
-import { Delete24Regular } from "@fluentui/react-icons";
+import { Delete24Regular, Edit24Regular } from "@fluentui/react-icons";
 
 export interface HistoryData {
     id: string;
@@ -14,25 +14,43 @@ interface HistoryItemProps {
     item: HistoryData;
     onSelect: (id: string) => void;
     onDelete: (id: string) => void;
+    onUpdateTitle: (id: string, title: string) => void;
 }
 
-export function HistoryItem({ item, onSelect, onDelete }: HistoryItemProps) {
-    const [isModalOpen, setIsModalOpen] = useState(false);
+export function HistoryItem({ item, onSelect, onDelete, onUpdateTitle }: HistoryItemProps) {
+    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
+    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
+    const [newTitle, setNewTitle] = useState(item.title);
 
     const handleDelete = useCallback(() => {
-        setIsModalOpen(false);
+        setIsDeleteModalOpen(false);
         onDelete(item.id);
     }, [item.id, onDelete]);
 
+    const handleUpdateTitle = useCallback(() => {
+        setIsEditModalOpen(false);
+        onUpdateTitle(item.id, newTitle);
+    }, [item.id, newTitle, onUpdateTitle]);
+
     return (
         <div className={styles.historyItem}>
             <button onClick={() => onSelect(item.id)} className={styles.historyItemButton}>
                 <div className={styles.historyItemTitle}>{item.title}</div>
             </button>
-            <button onClick={() => setIsModalOpen(true)} className={styles.deleteButton} aria-label="delete this chat history">
+            <button onClick={() => setIsEditModalOpen(true)} className={styles.editButton} aria-label="edit this chat history">
+                <Edit24Regular className={styles.editIcon} />
+            </button>
+            <button onClick={() => setIsDeleteModalOpen(true)} className={styles.deleteButton} aria-label="delete this chat history">
                 <Delete24Regular className={styles.deleteIcon} />
             </button>
-            <DeleteHistoryModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onConfirm={handleDelete} />
+            <DeleteHistoryModal isOpen={isDeleteModalOpen} onClose={() => setIsDeleteModalOpen(false)} onConfirm={handleDelete} />
+            <EditHistoryModal
+                isOpen={isEditModalOpen}
+                onClose={() => setIsEditModalOpen(false)}
+                newTitle={newTitle}
+                setNewTitle={setNewTitle}
+                onConfirm={handleUpdateTitle}
+            />
         </div>
     );
 }
@@ -57,3 +75,42 @@ function DeleteHistoryModal({ isOpen, onClose, onConfirm }: { isOpen: boolean; o
         </div>
     );
 }
+
+function EditHistoryModal({
+    isOpen,
+    onClose,
+    newTitle,
+    setNewTitle,
+    onConfirm
+}: {
+    isOpen: boolean;
+    onClose: () => void;
+    newTitle: string;
+    setNewTitle: (title: string) => void;
+    onConfirm: () => void;
+}) {
+    if (!isOpen) return null;
+    const { t } = useTranslation();
+    return (
+        <div className={styles.modalOverlay}>
+            <div className={styles.modalContent}>
+                <h2 className={styles.modalTitle}>{t("history.editModalTitle")}</h2>
+                <input
+                    type="text"
+                    value={newTitle}
+                    onChange={e => setNewTitle(e.target.value)}
+                    className={styles.modalInput}
+                    placeholder={t("history.editModalPlaceholder")}
+                />
+                <div className={styles.modalActions}>
+                    <DefaultButton onClick={onClose} className={styles.modalCancelButton}>
+                        {t("history.cancelLabel")}
+                    </DefaultButton>
+                    <DefaultButton onClick={onConfirm} className={styles.modalSubmitButton}>
+                        {t("history.submitLabel")}
+                    </DefaultButton>
+                </div>
+            </div>
+        </div>
+    );
+}
#### app/frontend/src/components/HistoryPanel/HistoryPanel.tsx
diff --git a/app/frontend/src/components/HistoryPanel/HistoryPanel.tsx b/app/frontend/src/components/HistoryPanel/HistoryPanel.tsx
index acaf3b7..16b8291 100644
--- a/app/frontend/src/components/HistoryPanel/HistoryPanel.tsx
+++ b/app/frontend/src/components/HistoryPanel/HistoryPanel.tsx
@@ -64,6 +64,12 @@ export const HistoryPanel = ({
         setHistory(prevHistory => prevHistory.filter(item => item.id !== id));
     };
 
+    const handleUpdateTitle = async (id: string, title: string) => {
+        const token = client ? await getToken(client) : undefined;
+        await historyManager.updateTitle(id, title, token);
+        setHistory(prevHistory => prevHistory.map(item => (item.id === id ? { ...item, title } : item)));
+    };
+
     const groupedHistory = useMemo(() => groupHistory(history), [history]);
 
     const { t } = useTranslation();
@@ -88,7 +94,7 @@ export const HistoryPanel = ({
                     <div key={group} className={styles.group}>
                         <p className={styles.groupLabel}>{t(group)}</p>
                         {items.map(item => (
-                            <HistoryItem key={item.id} item={item} onSelect={handleSelect} onDelete={handleDelete} />
+                            <HistoryItem key={item.id} item={item} onSelect={handleSelect} onDelete={handleDelete} onUpdateTitle={handleUpdateTitle} />
                         ))}
                     </div>
                 ))}
#### app/frontend/src/components/HistoryProviders/CosmosDB.ts
diff --git a/app/frontend/src/components/HistoryProviders/CosmosDB.ts b/app/frontend/src/components/HistoryProviders/CosmosDB.ts
index 5da9df5..82afd91 100644
--- a/app/frontend/src/components/HistoryProviders/CosmosDB.ts
+++ b/app/frontend/src/components/HistoryProviders/CosmosDB.ts
@@ -1,5 +1,5 @@
 import { IHistoryProvider, Answers, HistoryProviderOptions, HistoryMetaData } from "./IProvider";
-import { deleteChatHistoryApi, getChatHistoryApi, getChatHistoryListApi, postChatHistoryApi } from "../../api";
+import { deleteChatHistoryApi, getChatHistoryApi, getChatHistoryListApi, postChatHistoryApi, updateChatHistoryTitleApi } from "../../api";
 
 export class CosmosDBProvider implements IHistoryProvider {
     getProviderName = () => HistoryProviderOptions.CosmosDB;
@@ -48,4 +48,9 @@ export class CosmosDBProvider implements IHistoryProvider {
         await deleteChatHistoryApi(id, idToken || "");
         return;
     }
+
+    async updateTitle(id: string, title: string, idToken?: string): Promise<void> {
+        await updateChatHistoryTitleApi(id, title, idToken || "");
+        return;
+    }
 }
#### app/frontend/src/components/HistoryProviders/IProvider.ts
diff --git a/app/frontend/src/components/HistoryProviders/IProvider.ts b/app/frontend/src/components/HistoryProviders/IProvider.ts
index 026443d..64b47ec 100644
--- a/app/frontend/src/components/HistoryProviders/IProvider.ts
+++ b/app/frontend/src/components/HistoryProviders/IProvider.ts
@@ -16,4 +16,5 @@ export interface IHistoryProvider {
     addItem(id: string, answers: Answers, idToken?: string): Promise<void>;
     getItem(id: string, idToken?: string): Promise<Answers | null>;
     deleteItem(id: string, idToken?: string): Promise<void>;
+    updateTitle(id: string, title: string, idToken?: string): Promise<void>;
 }
#### app/frontend/src/components/HistoryProviders/IndexedDB.ts
diff --git a/app/frontend/src/components/HistoryProviders/IndexedDB.ts b/app/frontend/src/components/HistoryProviders/IndexedDB.ts
index ca8fa19..c35baad 100644
--- a/app/frontend/src/components/HistoryProviders/IndexedDB.ts
+++ b/app/frontend/src/components/HistoryProviders/IndexedDB.ts
@@ -101,4 +101,15 @@ export class IndexedDBProvider implements IHistoryProvider {
         await db.delete(this.storeName, id);
         return;
     }
+
+    async updateTitle(id: string, title: string): Promise<void> {
+        const db = await this.init();
+        const tx = db.transaction(this.storeName, "readwrite");
+        const item = await tx.objectStore(this.storeName).get(id);
+        if (item) {
+            item.title = title;
+            await tx.objectStore(this.storeName).put(item);
+        }
+        await tx.done;
+    }
 }
#### app/frontend/src/components/HistoryProviders/None.ts
diff --git a/app/frontend/src/components/HistoryProviders/None.ts b/app/frontend/src/components/HistoryProviders/None.ts
index a662d54..0f95ad1 100644
--- a/app/frontend/src/components/HistoryProviders/None.ts
+++ b/app/frontend/src/components/HistoryProviders/None.ts
@@ -17,4 +17,7 @@ export class NoneProvider implements IHistoryProvider {
     async deleteItem(id: string): Promise<void> {
         return;
     }
+    async updateTitle(id: string, title: string): Promise<void> {
+        return;
+    }
 }
#### app/frontend/src/locales/en/translation.json
diff --git a/app/frontend/src/locales/en/translation.json b/app/frontend/src/locales/en/translation.json
index 094fc22..359a6ca 100644
--- a/app/frontend/src/locales/en/translation.json
+++ b/app/frontend/src/locales/en/translation.json
@@ -12,8 +12,11 @@
         "noHistory": "No chat history",
         "deleteModalTitle": "Delete chat history",
         "deleteModalDescription": "This action cannot be undone. Delete this chat history?",
+        "editModalTitle": "Enter a new conversation name:",
+        "editModalPlaceholder": "ex: 'Income Calculations'",
         "deleteLabel": "Delete",
         "cancelLabel": "Cancel",
+        "submitLabel": "Submit",
         "today": "Today",
         "yesterday": "Yesterday",
         "last7days": "Last 7 days",
#### app/frontend/src/pages/chat/Chat.module.css
diff --git a/app/frontend/src/pages/chat/Chat.module.css b/app/frontend/src/pages/chat/Chat.module.css
index 77a00ae..514d9b8 100644
--- a/app/frontend/src/pages/chat/Chat.module.css
+++ b/app/frontend/src/pages/chat/Chat.module.css
@@ -16,7 +16,7 @@
     flex-direction: column;
     align-items: center;
     width: 100%;
-    max-height: calc(100vh - 10rem);
+    max-height: 100%;
 }
 
 .chatEmptyState {
#### app/frontend/src/pages/layout/Layout.module.css
diff --git a/app/frontend/src/pages/layout/Layout.module.css b/app/frontend/src/pages/layout/Layout.module.css
index 7a86702..bd6d3b0 100644
--- a/app/frontend/src/pages/layout/Layout.module.css
+++ b/app/frontend/src/pages/layout/Layout.module.css
@@ -6,6 +6,8 @@
 
 .content {
     flex: 1;
+    padding: 0;
+    margin: 0;
 }
 
 .header {
#### infra/main.bicep
diff --git a/infra/main.bicep b/infra/main.bicep
index f305f64..c890dde 100644
--- a/infra/main.bicep
+++ b/infra/main.bicep
@@ -857,7 +857,7 @@ module cosmosDb 'br/public:avm/res/document-db/database-account:0.6.1' = if (use
                 }
                 {
                   path: '/type/?'
-                }
+                }                
               ]
               excludedPaths: [
                 {
@@ -865,6 +865,7 @@ module cosmosDb 'br/public:avm/res/document-db/database-account:0.6.1' = if (use
                 }
               ]
             }
+            defaultTtl:-1
           }
         ]
       }


---
Generated on: 2025-02-25 10:51:05

### Changes made:

- app/frontend/src/components/Example/Example.module.css
- app/frontend/src/components/Footer/Footer.module.css
- app/frontend/src/pages/chat/Chat.module.css
- app/frontend/src/pages/layout/Layout.module.css

### Detailed changes:

#### app/frontend/src/components/Example/Example.module.css
diff --git a/app/frontend/src/components/Example/Example.module.css b/app/frontend/src/components/Example/Example.module.css
index 0ab3f10..dab8aec 100644
--- a/app/frontend/src/components/Example/Example.module.css
+++ b/app/frontend/src/components/Example/Example.module.css
@@ -48,6 +48,8 @@
         flex-direction: row; /* Switch to row layout for wider screens */
         padding-left: 0;
         padding-right: 0;
+        margin-left: 1rem;
+        margin-right: 1rem;
     }
 
     .example {
@@ -60,9 +62,11 @@
         display: block; /* Show an additional list item for medium heights */
     }
     .exampleText {
-        font-size: 1.375rem;
-        width: 17.5rem;
+        font-size: 1.1rem;
+        font-weight: 600;
+        width: 15.5rem;
         padding: 0;
-        min-height: 6.25rem;
+        color: rgb(75, 94, 196);
+        min-height: 2.25rem;
     }
 }
#### app/frontend/src/components/Footer/Footer.module.css
diff --git a/app/frontend/src/components/Footer/Footer.module.css b/app/frontend/src/components/Footer/Footer.module.css
index 6eec09f..3107f3b 100644
--- a/app/frontend/src/components/Footer/Footer.module.css
+++ b/app/frontend/src/components/Footer/Footer.module.css
@@ -5,6 +5,8 @@
     padding: 1rem;
     background-color: #000000; /* Adjust the background color to match your header */
     color: white; /* Set the text color to white */
+    font-size: smaller;
+    width: 100%;
 }
 
 .logo {
#### app/frontend/src/pages/chat/Chat.module.css
diff --git a/app/frontend/src/pages/chat/Chat.module.css b/app/frontend/src/pages/chat/Chat.module.css
index 8ee0840..77a00ae 100644
--- a/app/frontend/src/pages/chat/Chat.module.css
+++ b/app/frontend/src/pages/chat/Chat.module.css
@@ -32,8 +32,9 @@
 .chatEmptyStateTitle {
     font-size: 1.75rem;
     font-weight: 600;
-    margin-top: 1;
+    margin-top: 0.5rem;
     margin-bottom: 0rem;
+    color: rgb(75, 94, 196);
 }
 
 .chatEmptyStateSubtitle {
@@ -122,11 +123,11 @@
     }
 
     .chatEmptyState {
-        padding-top: 3.75rem;
+        padding-top: 0.75rem;
     }
 
     .chatEmptyStateTitle {
-        font-size: 3rem;
+        font-size: 2.5rem;
     }
 
     .chatInput {
#### app/frontend/src/pages/layout/Layout.module.css
diff --git a/app/frontend/src/pages/layout/Layout.module.css b/app/frontend/src/pages/layout/Layout.module.css
index f78c147..7a86702 100644
--- a/app/frontend/src/pages/layout/Layout.module.css
+++ b/app/frontend/src/pages/layout/Layout.module.css
@@ -1,7 +1,7 @@
 .layout {
     display: flex;
     flex-direction: column;
-    height: 100%;
+    min-height: 100vh;
 }
 
 .content {


---
Generated on: 2025-02-24 20:44:00

### Changes made:

- app/frontend/src/pages/layout/Layout.module.css
- app/frontend/src/pages/layout/Layout.tsx

### Detailed changes:

#### app/frontend/src/pages/layout/Layout.module.css
diff --git a/app/frontend/src/pages/layout/Layout.module.css b/app/frontend/src/pages/layout/Layout.module.css
index 6242bbf..d708e18 100644
--- a/app/frontend/src/pages/layout/Layout.module.css
+++ b/app/frontend/src/pages/layout/Layout.module.css
@@ -51,7 +51,8 @@
 .headerNavList {
     z-index: 100;
     display: none;
-    flex-direction: column;
+    flex-direction: row;
+    gap: 1rem;
     background-color: #222222;
     position: absolute;
     top: 2.7rem;
@@ -70,6 +71,7 @@
 
 .headerNavList.show {
     display: flex; /* Show when toggled */
+    flex-direction: column;
 }
 
 .headerNavPageLink {
@@ -119,7 +121,7 @@
 .loginMenuContainer {
     display: flex;
     align-items: center;
-    gap: 0; /* Ensure no gap between login button and menu toggle */
+    gap: 0.25rem;
 }
 
 @media (min-width: 992px) {
#### app/frontend/src/pages/layout/Layout.tsx
diff --git a/app/frontend/src/pages/layout/Layout.tsx b/app/frontend/src/pages/layout/Layout.tsx
index 9f1a648..bc4897d 100644
--- a/app/frontend/src/pages/layout/Layout.tsx
+++ b/app/frontend/src/pages/layout/Layout.tsx
@@ -51,7 +51,7 @@ const Layout = () => {
                         <ul className={`${styles.headerNavList} ${menuOpen ? styles.show : ""}`}>
                             <li>
                                 <a
-                                    style={{ color: "white" }}
+                                    style={{ color: "white", background: "black" }}
                                     target="_blank"
                                     href="https://auth.sharefile.io/mortgagemanuals/login?returnUrl=%2fconnect%2fauthorize%2fcallback%3fclient_id%3dDzi4UPUAg5l8beKdioecdcnmHUTWWln6%26state%3dPnMKwy8LBandoWH9yApWcw--%26acr_values%3dtenant%253Amortgagemanuals%26response_type%3dcode%26redirect_uri%3dhttps%253A%252F%252Fmortgagemanuals.sharefile.com%252Flogin%252Foauthlogin%26scope%3dsharefile%253Arestapi%253Av3%2520sharefile%253Arestapi%253Av3-internal%2520offline_access%2520openid"
                                 >
@@ -59,7 +59,11 @@ const Layout = () => {
                                 </a>
                             </li>
                             <li>
-                                <a href="https://vm.providesupport.com/0vqlme5nawdpd03rg1k9jutxt2" target="_blank" className={styles.externalLink}>
+                                <a
+                                    href="https://vm.providesupport.com/0vqlme5nawdpd03rg1k9jutxt2"
+                                    target="_blank"
+                                    style={{ color: "white", background: "black" }}
+                                >
                                     Need Help?
                                 </a>
                             </li>


---
Generated on: 2025-02-24 19:58:53

### Changes made:

- app/frontend/src/components/LoginButton/LoginButton.module.css
- app/frontend/src/pages/chat/Chat.tsx
- app/frontend/src/pages/layout/Layout.module.css
- app/frontend/src/pages/layout/Layout.tsx
- infra/main.bicep

### Detailed changes:

#### app/frontend/src/components/LoginButton/LoginButton.module.css
diff --git a/app/frontend/src/components/LoginButton/LoginButton.module.css b/app/frontend/src/components/LoginButton/LoginButton.module.css
index d2222b3..232f90c 100644
--- a/app/frontend/src/components/LoginButton/LoginButton.module.css
+++ b/app/frontend/src/components/LoginButton/LoginButton.module.css
@@ -1,7 +1,7 @@
 .loginButton {
     border-radius: 0.3125em;
     font-weight: 100;
-    font-size: 1rem;
+    font-size: 0.75rem;
     margin: 0;
     padding-left: 0.25rem;
     padding-right: 0.25rem;
#### app/frontend/src/pages/chat/Chat.tsx
diff --git a/app/frontend/src/pages/chat/Chat.tsx b/app/frontend/src/pages/chat/Chat.tsx
index ed46aa3..231e3e9 100644
--- a/app/frontend/src/pages/chat/Chat.tsx
+++ b/app/frontend/src/pages/chat/Chat.tsx
@@ -3,8 +3,6 @@ import { useTranslation } from "react-i18next";
 import { Helmet } from "react-helmet-async";
 import { Panel, DefaultButton } from "@fluentui/react";
 import readNDJSONStream from "ndjson-readablestream";
-
-import appLogo from "../../assets/applogo.png";
 import styles from "./Chat.module.css";
 
 import {
#### app/frontend/src/pages/layout/Layout.module.css
diff --git a/app/frontend/src/pages/layout/Layout.module.css b/app/frontend/src/pages/layout/Layout.module.css
index bd9ec18..6ce231e 100644
--- a/app/frontend/src/pages/layout/Layout.module.css
+++ b/app/frontend/src/pages/layout/Layout.module.css
@@ -4,8 +4,12 @@
     height: 100%;
 }
 
+.content {
+    flex: 1;
+}
+
 .header {
-    background-color: #222222;
+    background-color: #000000;
     color: #f2f2f2;
 }
 
@@ -50,6 +54,12 @@
     align-items: flex-end;
 }
 
+@media (max-width: 991px) {
+    .headerNavList {
+        display: none;
+    }
+}
+
 .headerNavList.show {
     display: flex; /* Show when toggled */
 }
@@ -79,6 +89,11 @@
     padding: 1rem;
 }
 
+.externalLink {
+    color: #ffffff;
+    padding: 1rem;
+}
+
 .headerNavLeftMargin {
     display: none;
 }
#### app/frontend/src/pages/layout/Layout.tsx
diff --git a/app/frontend/src/pages/layout/Layout.tsx b/app/frontend/src/pages/layout/Layout.tsx
index 72ade3c..6fa3d30 100644
--- a/app/frontend/src/pages/layout/Layout.tsx
+++ b/app/frontend/src/pages/layout/Layout.tsx
@@ -6,6 +6,7 @@ import styles from "./Layout.module.css";
 import { useLogin } from "../../authConfig";
 
 import { LoginButton } from "../../components/LoginButton";
+import { Footer } from "../../components/Footer/Footer";
 import { IconButton } from "@fluentui/react";
 
 const Layout = () => {
@@ -41,28 +42,24 @@ const Layout = () => {
                     <Link to="/" className={styles.headerTitleContainer}>
                         <h3 className={styles.headerTitle}>{t("headerTitle")}</h3>
                     </Link>
-                    {/* <nav>
+                    <nav>
                         <ul className={`${styles.headerNavList} ${menuOpen ? styles.show : ""}`}>
                             <li>
-                                <NavLink
-                                    to="/"
-                                    className={({ isActive }) => (isActive ? styles.headerNavPageLinkActive : styles.headerNavPageLink)}
-                                    onClick={() => setMenuOpen(false)}
+                                <a
+                                    style={{ color: "white" }}
+                                    target="_blank"
+                                    href="https://auth.sharefile.io/mortgagemanuals/login?returnUrl=%2fconnect%2fauthorize%2fcallback%3fclient_id%3dDzi4UPUAg5l8beKdioecdcnmHUTWWln6%26state%3dPnMKwy8LBandoWH9yApWcw--%26acr_values%3dtenant%253Amortgagemanuals%26response_type%3dcode%26redirect_uri%3dhttps%253A%252F%252Fmortgagemanuals.sharefile.com%252Flogin%252Foauthlogin%26scope%3dsharefile%253Arestapi%253Av3%2520sharefile%253Arestapi%253Av3-internal%2520offline_access%2520openid"
                                 >
-                                    {t("chat")}
-                                </NavLink>
+                                    Policy Documents
+                                </a>
                             </li>
                             <li>
-                                <NavLink
-                                    to="/qa"
-                                    className={({ isActive }) => (isActive ? styles.headerNavPageLinkActive : styles.headerNavPageLink)}
-                                    onClick={() => setMenuOpen(false)}
-                                >
-                                    {t("qa")}
-                                </NavLink>
+                                <a href="https://vm.providesupport.com/0vqlme5nawdpd03rg1k9jutxt2" target="_blank" className={styles.externalLink}>
+                                    Need Help?
+                                </a>
                             </li>
                         </ul>
-                    </nav> */}
+                    </nav>
                     <div className={styles.loginMenuContainer}>
                         {useLogin && <LoginButton />}
                         <IconButton
@@ -74,8 +71,10 @@ const Layout = () => {
                     </div>
                 </div>
             </header>
-
-            <Outlet />
+            <main className={styles.content}>
+                <Outlet />
+            </main>
+            <Footer />
         </div>
     );
 };
#### infra/main.bicep
diff --git a/infra/main.bicep b/infra/main.bicep
index a9cb352..f305f64 100644
--- a/infra/main.bicep
+++ b/infra/main.bicep
@@ -53,7 +53,7 @@ param azureOpenAiCustomUrl string = ''
 param azureOpenAiApiVersion string = ''
 @secure()
 param azureOpenAiApiKey string = ''
-param azureOpenAiDisableKeys bool = true
+param azureOpenAiDisableKeys bool = false
 param openAiServiceName string = ''
 param openAiResourceGroupName string = ''
 


---
Generated on: 2025-02-24 13:46:29

### Changes made:

- .azure/pai-mm-prod/.env-temp
- CHANGELOG.md
- app/backend/prepdocslib/searchmanager.py
- scripts/generate_git_commit_message.py

### Detailed changes:

#### .azure/pai-mm-prod/.env-temp
diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
index adad91f..2983b9f 100644
--- a/.azure/pai-mm-prod/.env-temp
+++ b/.azure/pai-mm-prod/.env-temp
@@ -1,5 +1,4 @@
 AZURE_AUTH_TENANT_ID=""
-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
 AZURE_COSMOSDB_LOCATION="centralus"
 AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
 AZURE_ENFORCE_ACCESS_CONTROL="true"
#### CHANGELOG.md
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 4028629..e1deb67 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -1,3 +1,640 @@
+---
+Generated on: 2025-02-24 13:46:12
+
+### Changes made:
+
+- .azure/pai-mm-prod/.env-temp
+- CHANGELOG.md
+- app/backend/prepdocslib/searchmanager.py
+- scripts/generate_git_commit_message.py
+
+### Detailed changes:
+
+#### .azure/pai-mm-prod/.env-temp
+diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
+index adad91f..2983b9f 100644
+--- a/.azure/pai-mm-prod/.env-temp
++++ b/.azure/pai-mm-prod/.env-temp
+@@ -1,5 +1,4 @@
+ AZURE_AUTH_TENANT_ID=""
+-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
+ AZURE_COSMOSDB_LOCATION="centralus"
+ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
+ AZURE_ENFORCE_ACCESS_CONTROL="true"
+#### CHANGELOG.md
+diff --git a/CHANGELOG.md b/CHANGELOG.md
+index 4028629..0b174a3 100644
+--- a/CHANGELOG.md
++++ b/CHANGELOG.md
+@@ -1,3 +1,214 @@
++---
++Generated on: 2025-02-24 13:46:08
++
++### Changes made:
++
++- .azure/pai-mm-prod/.env-temp
++- CHANGELOG.md
++- app/backend/prepdocslib/searchmanager.py
++- scripts/generate_git_commit_message.py
++
++### Detailed changes:
++
++#### .azure/pai-mm-prod/.env-temp
++diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
++index adad91f..2983b9f 100644
++--- a/.azure/pai-mm-prod/.env-temp
+++++ b/.azure/pai-mm-prod/.env-temp
++@@ -1,5 +1,4 @@
++ AZURE_AUTH_TENANT_ID=""
++-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
++ AZURE_COSMOSDB_LOCATION="centralus"
++ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
++ AZURE_ENFORCE_ACCESS_CONTROL="true"
++#### CHANGELOG.md
++diff --git a/CHANGELOG.md b/CHANGELOG.md
++index 4028629..e7e4c54 100644
++--- a/CHANGELOG.md
+++++ b/CHANGELOG.md
++@@ -2151,3 +2151,101 @@ index dd2d488..44a233f 100644
++ \ No newline at end of file
++ 
++ 
+++---
+++Generated on: 2025-02-24 13:41:14
+++
+++### Changes made:
+++
+++- .azure/pai-mm-prod/.env-temp
+++- app/backend/prepdocslib/searchmanager.py
+++- scripts/generate_git_commit_message.py
+++
+++### Detailed changes:
+++
+++#### .azure/pai-mm-prod/.env-temp
+++diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
+++index adad91f..2983b9f 100644
+++--- a/.azure/pai-mm-prod/.env-temp
++++++ b/.azure/pai-mm-prod/.env-temp
+++@@ -1,5 +1,4 @@
+++ AZURE_AUTH_TENANT_ID=""
+++-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
+++ AZURE_COSMOSDB_LOCATION="centralus"
+++ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
+++ AZURE_ENFORCE_ACCESS_CONTROL="true"
+++#### app/backend/prepdocslib/searchmanager.py
+++diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
+++index f75af03..314e4fd 100644
+++--- a/app/backend/prepdocslib/searchmanager.py
++++++ b/app/backend/prepdocslib/searchmanager.py
+++@@ -103,7 +103,11 @@ class SearchManager:
+++                         vector_search_dimensions=self.embedding_dimensions,
+++                         vector_search_profile_name="embedding_config",
+++                     ),
+++-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
++++                    SimpleField(
++++                        name="category", 
++++                        type="Edm.String", 
++++                        filterable=True, 
++++                        facetable=True),
+++                     SimpleField(
+++                         name="sourcepage",
+++                         type="Edm.String",
+++@@ -122,22 +126,18 @@ class SearchManager:
+++                         filterable=True,
+++                         facetable=False,
+++                     ),
+++-                ]
+++-                if self.use_acls:
+++-                    fields.append(
+++-                        SimpleField(
+++-                            name="oids",
+++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++-                            filterable=True,
+++-                        )
+++-                    )
+++-                    fields.append(
+++-                        SimpleField(
+++-                            name="groups",
+++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++-                            filterable=True,
+++-                        )
++++                    SimpleField(
++++                        name="oids",
++++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++++                        filterable=True,
++++                    ),
++++                    SimpleField(
++++                        name="groups",
++++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++++                        filterable=True,
+++                     )
++++                ]
++++                    
+++                 if self.use_int_vectorization:
+++                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
+++                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
+++#### scripts/generate_git_commit_message.py
+++diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
+++index 171fb03..00790e8 100644
+++--- a/scripts/generate_git_commit_message.py
++++++ b/scripts/generate_git_commit_message.py
+++@@ -27,11 +27,11 @@ def get_file_diff(file_path):
+++ 
+++ def prepend_to_changelog(new_content):
+++     changelog_path = "CHANGELOG.md"
+++-    # if os.path.exists(changelog_path):
+++-    #     with open(changelog_path, "r") as f:
+++-    #         existing_content = f.read()
+++-    # else:
+++-    #     existing_content = ""
++++    if os.path.exists(changelog_path):
++++        with open(changelog_path, "r") as f:
++++            existing_content = f.read()
++++    else:
++++        existing_content = ""
+++ 
+++     with open(changelog_path, "a") as f:
+++         f.write(new_content + "\n\n")
+++
+++
++#### app/backend/prepdocslib/searchmanager.py
++diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
++index f75af03..314e4fd 100644
++--- a/app/backend/prepdocslib/searchmanager.py
+++++ b/app/backend/prepdocslib/searchmanager.py
++@@ -103,7 +103,11 @@ class SearchManager:
++                         vector_search_dimensions=self.embedding_dimensions,
++                         vector_search_profile_name="embedding_config",
++                     ),
++-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
+++                    SimpleField(
+++                        name="category", 
+++                        type="Edm.String", 
+++                        filterable=True, 
+++                        facetable=True),
++                     SimpleField(
++                         name="sourcepage",
++                         type="Edm.String",
++@@ -122,22 +126,18 @@ class SearchManager:
++                         filterable=True,
++                         facetable=False,
++                     ),
++-                ]
++-                if self.use_acls:
++-                    fields.append(
++-                        SimpleField(
++-                            name="oids",
++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++-                            filterable=True,
++-                        )
++-                    )
++-                    fields.append(
++-                        SimpleField(
++-                            name="groups",
++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++-                            filterable=True,
++-                        )
+++                    SimpleField(
+++                        name="oids",
+++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++                        filterable=True,
+++                    ),
+++                    SimpleField(
+++                        name="groups",
+++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++                        filterable=True,
++                     )
+++                ]
+++                    
++                 if self.use_int_vectorization:
++                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
++                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
++#### scripts/generate_git_commit_message.py
++diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
++index 171fb03..13254af 100644
++--- a/scripts/generate_git_commit_message.py
+++++ b/scripts/generate_git_commit_message.py
++@@ -27,14 +27,14 @@ def get_file_diff(file_path):
++ 
++ def prepend_to_changelog(new_content):
++     changelog_path = "CHANGELOG.md"
++-    # if os.path.exists(changelog_path):
++-    #     with open(changelog_path, "r") as f:
++-    #         existing_content = f.read()
++-    # else:
++-    #     existing_content = ""
+++    if os.path.exists(changelog_path):
+++        with open(changelog_path, "r") as f:
+++            existing_content = f.read()
+++    else:
+++        existing_content = ""
++ 
++-    with open(changelog_path, "a") as f:
++-        f.write(new_content + "\n\n")
+++    with open(changelog_path, "w") as f:
+++        f.write(new_content + "\n\n" + existing_content)
++ 
++ def main():
++     repo_path = os.getcwd()
++
++
+ ---
+ Generated on: 2025-02-24 12:05:03
+ 
+@@ -2151,3 +2362,101 @@ index dd2d488..44a233f 100644
+ \ No newline at end of file
+ 
+ 
++---
++Generated on: 2025-02-24 13:41:14
++
++### Changes made:
++
++- .azure/pai-mm-prod/.env-temp
++- app/backend/prepdocslib/searchmanager.py
++- scripts/generate_git_commit_message.py
++
++### Detailed changes:
++
++#### .azure/pai-mm-prod/.env-temp
++diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
++index adad91f..2983b9f 100644
++--- a/.azure/pai-mm-prod/.env-temp
+++++ b/.azure/pai-mm-prod/.env-temp
++@@ -1,5 +1,4 @@
++ AZURE_AUTH_TENANT_ID=""
++-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
++ AZURE_COSMOSDB_LOCATION="centralus"
++ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
++ AZURE_ENFORCE_ACCESS_CONTROL="true"
++#### app/backend/prepdocslib/searchmanager.py
++diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
++index f75af03..314e4fd 100644
++--- a/app/backend/prepdocslib/searchmanager.py
+++++ b/app/backend/prepdocslib/searchmanager.py
++@@ -103,7 +103,11 @@ class SearchManager:
++                         vector_search_dimensions=self.embedding_dimensions,
++                         vector_search_profile_name="embedding_config",
++                     ),
++-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
+++                    SimpleField(
+++                        name="category", 
+++                        type="Edm.String", 
+++                        filterable=True, 
+++                        facetable=True),
++                     SimpleField(
++                         name="sourcepage",
++                         type="Edm.String",
++@@ -122,22 +126,18 @@ class SearchManager:
++                         filterable=True,
++                         facetable=False,
++                     ),
++-                ]
++-                if self.use_acls:
++-                    fields.append(
++-                        SimpleField(
++-                            name="oids",
++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++-                            filterable=True,
++-                        )
++-                    )
++-                    fields.append(
++-                        SimpleField(
++-                            name="groups",
++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++-                            filterable=True,
++-                        )
+++                    SimpleField(
+++                        name="oids",
+++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++                        filterable=True,
+++                    ),
+++                    SimpleField(
+++                        name="groups",
+++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++                        filterable=True,
++                     )
+++                ]
+++                    
++                 if self.use_int_vectorization:
++                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
++                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
++#### scripts/generate_git_commit_message.py
++diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
++index 171fb03..00790e8 100644
++--- a/scripts/generate_git_commit_message.py
+++++ b/scripts/generate_git_commit_message.py
++@@ -27,11 +27,11 @@ def get_file_diff(file_path):
++ 
++ def prepend_to_changelog(new_content):
++     changelog_path = "CHANGELOG.md"
++-    # if os.path.exists(changelog_path):
++-    #     with open(changelog_path, "r") as f:
++-    #         existing_content = f.read()
++-    # else:
++-    #     existing_content = ""
+++    if os.path.exists(changelog_path):
+++        with open(changelog_path, "r") as f:
+++            existing_content = f.read()
+++    else:
+++        existing_content = ""
++ 
++     with open(changelog_path, "a") as f:
++         f.write(new_content + "\n\n")
++
++
+#### app/backend/prepdocslib/searchmanager.py
+diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
+index f75af03..314e4fd 100644
+--- a/app/backend/prepdocslib/searchmanager.py
++++ b/app/backend/prepdocslib/searchmanager.py
+@@ -103,7 +103,11 @@ class SearchManager:
+                         vector_search_dimensions=self.embedding_dimensions,
+                         vector_search_profile_name="embedding_config",
+                     ),
+-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
++                    SimpleField(
++                        name="category", 
++                        type="Edm.String", 
++                        filterable=True, 
++                        facetable=True),
+                     SimpleField(
+                         name="sourcepage",
+                         type="Edm.String",
+@@ -122,22 +126,18 @@ class SearchManager:
+                         filterable=True,
+                         facetable=False,
+                     ),
+-                ]
+-                if self.use_acls:
+-                    fields.append(
+-                        SimpleField(
+-                            name="oids",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
+-                    )
+-                    fields.append(
+-                        SimpleField(
+-                            name="groups",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
++                    SimpleField(
++                        name="oids",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
++                    ),
++                    SimpleField(
++                        name="groups",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
+                     )
++                ]
++                    
+                 if self.use_int_vectorization:
+                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
+                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
+#### scripts/generate_git_commit_message.py
+diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
+index 171fb03..13254af 100644
+--- a/scripts/generate_git_commit_message.py
++++ b/scripts/generate_git_commit_message.py
+@@ -27,14 +27,14 @@ def get_file_diff(file_path):
+ 
+ def prepend_to_changelog(new_content):
+     changelog_path = "CHANGELOG.md"
+-    # if os.path.exists(changelog_path):
+-    #     with open(changelog_path, "r") as f:
+-    #         existing_content = f.read()
+-    # else:
+-    #     existing_content = ""
++    if os.path.exists(changelog_path):
++        with open(changelog_path, "r") as f:
++            existing_content = f.read()
++    else:
++        existing_content = ""
+ 
+-    with open(changelog_path, "a") as f:
+-        f.write(new_content + "\n\n")
++    with open(changelog_path, "w") as f:
++        f.write(new_content + "\n\n" + existing_content)
+ 
+ def main():
+     repo_path = os.getcwd()
+
+
+---
+Generated on: 2025-02-24 13:46:08
+
+### Changes made:
+
+- .azure/pai-mm-prod/.env-temp
+- CHANGELOG.md
+- app/backend/prepdocslib/searchmanager.py
+- scripts/generate_git_commit_message.py
+
+### Detailed changes:
+
+#### .azure/pai-mm-prod/.env-temp
+diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
+index adad91f..2983b9f 100644
+--- a/.azure/pai-mm-prod/.env-temp
++++ b/.azure/pai-mm-prod/.env-temp
+@@ -1,5 +1,4 @@
+ AZURE_AUTH_TENANT_ID=""
+-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
+ AZURE_COSMOSDB_LOCATION="centralus"
+ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
+ AZURE_ENFORCE_ACCESS_CONTROL="true"
+#### CHANGELOG.md
+diff --git a/CHANGELOG.md b/CHANGELOG.md
+index 4028629..e7e4c54 100644
+--- a/CHANGELOG.md
++++ b/CHANGELOG.md
+@@ -2151,3 +2151,101 @@ index dd2d488..44a233f 100644
+ \ No newline at end of file
+ 
+ 
++---
++Generated on: 2025-02-24 13:41:14
++
++### Changes made:
++
++- .azure/pai-mm-prod/.env-temp
++- app/backend/prepdocslib/searchmanager.py
++- scripts/generate_git_commit_message.py
++
++### Detailed changes:
++
++#### .azure/pai-mm-prod/.env-temp
++diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
++index adad91f..2983b9f 100644
++--- a/.azure/pai-mm-prod/.env-temp
+++++ b/.azure/pai-mm-prod/.env-temp
++@@ -1,5 +1,4 @@
++ AZURE_AUTH_TENANT_ID=""
++-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
++ AZURE_COSMOSDB_LOCATION="centralus"
++ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
++ AZURE_ENFORCE_ACCESS_CONTROL="true"
++#### app/backend/prepdocslib/searchmanager.py
++diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
++index f75af03..314e4fd 100644
++--- a/app/backend/prepdocslib/searchmanager.py
+++++ b/app/backend/prepdocslib/searchmanager.py
++@@ -103,7 +103,11 @@ class SearchManager:
++                         vector_search_dimensions=self.embedding_dimensions,
++                         vector_search_profile_name="embedding_config",
++                     ),
++-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
+++                    SimpleField(
+++                        name="category", 
+++                        type="Edm.String", 
+++                        filterable=True, 
+++                        facetable=True),
++                     SimpleField(
++                         name="sourcepage",
++                         type="Edm.String",
++@@ -122,22 +126,18 @@ class SearchManager:
++                         filterable=True,
++                         facetable=False,
++                     ),
++-                ]
++-                if self.use_acls:
++-                    fields.append(
++-                        SimpleField(
++-                            name="oids",
++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++-                            filterable=True,
++-                        )
++-                    )
++-                    fields.append(
++-                        SimpleField(
++-                            name="groups",
++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++-                            filterable=True,
++-                        )
+++                    SimpleField(
+++                        name="oids",
+++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++                        filterable=True,
+++                    ),
+++                    SimpleField(
+++                        name="groups",
+++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++                        filterable=True,
++                     )
+++                ]
+++                    
++                 if self.use_int_vectorization:
++                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
++                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
++#### scripts/generate_git_commit_message.py
++diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
++index 171fb03..00790e8 100644
++--- a/scripts/generate_git_commit_message.py
+++++ b/scripts/generate_git_commit_message.py
++@@ -27,11 +27,11 @@ def get_file_diff(file_path):
++ 
++ def prepend_to_changelog(new_content):
++     changelog_path = "CHANGELOG.md"
++-    # if os.path.exists(changelog_path):
++-    #     with open(changelog_path, "r") as f:
++-    #         existing_content = f.read()
++-    # else:
++-    #     existing_content = ""
+++    if os.path.exists(changelog_path):
+++        with open(changelog_path, "r") as f:
+++            existing_content = f.read()
+++    else:
+++        existing_content = ""
++ 
++     with open(changelog_path, "a") as f:
++         f.write(new_content + "\n\n")
++
++
+#### app/backend/prepdocslib/searchmanager.py
+diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
+index f75af03..314e4fd 100644
+--- a/app/backend/prepdocslib/searchmanager.py
++++ b/app/backend/prepdocslib/searchmanager.py
+@@ -103,7 +103,11 @@ class SearchManager:
+                         vector_search_dimensions=self.embedding_dimensions,
+                         vector_search_profile_name="embedding_config",
+                     ),
+-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
++                    SimpleField(
++                        name="category", 
++                        type="Edm.String", 
++                        filterable=True, 
++                        facetable=True),
+                     SimpleField(
+                         name="sourcepage",
+                         type="Edm.String",
+@@ -122,22 +126,18 @@ class SearchManager:
+                         filterable=True,
+                         facetable=False,
+                     ),
+-                ]
+-                if self.use_acls:
+-                    fields.append(
+-                        SimpleField(
+-                            name="oids",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
+-                    )
+-                    fields.append(
+-                        SimpleField(
+-                            name="groups",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
++                    SimpleField(
++                        name="oids",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
++                    ),
++                    SimpleField(
++                        name="groups",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
+                     )
++                ]
++                    
+                 if self.use_int_vectorization:
+                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
+                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
+#### scripts/generate_git_commit_message.py
+diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
+index 171fb03..13254af 100644
+--- a/scripts/generate_git_commit_message.py
++++ b/scripts/generate_git_commit_message.py
+@@ -27,14 +27,14 @@ def get_file_diff(file_path):
+ 
+ def prepend_to_changelog(new_content):
+     changelog_path = "CHANGELOG.md"
+-    # if os.path.exists(changelog_path):
+-    #     with open(changelog_path, "r") as f:
+-    #         existing_content = f.read()
+-    # else:
+-    #     existing_content = ""
++    if os.path.exists(changelog_path):
++        with open(changelog_path, "r") as f:
++            existing_content = f.read()
++    else:
++        existing_content = ""
+ 
+-    with open(changelog_path, "a") as f:
+-        f.write(new_content + "\n\n")
++    with open(changelog_path, "w") as f:
++        f.write(new_content + "\n\n" + existing_content)
+ 
+ def main():
+     repo_path = os.getcwd()
+
+
 ---
 Generated on: 2025-02-24 12:05:03
 
@@ -2151,3 +2788,101 @@ index dd2d488..44a233f 100644
 \ No newline at end of file
 
 
+---
+Generated on: 2025-02-24 13:41:14
+
+### Changes made:
+
+- .azure/pai-mm-prod/.env-temp
+- app/backend/prepdocslib/searchmanager.py
+- scripts/generate_git_commit_message.py
+
+### Detailed changes:
+
+#### .azure/pai-mm-prod/.env-temp
+diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
+index adad91f..2983b9f 100644
+--- a/.azure/pai-mm-prod/.env-temp
++++ b/.azure/pai-mm-prod/.env-temp
+@@ -1,5 +1,4 @@
+ AZURE_AUTH_TENANT_ID=""
+-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
+ AZURE_COSMOSDB_LOCATION="centralus"
+ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
+ AZURE_ENFORCE_ACCESS_CONTROL="true"
+#### app/backend/prepdocslib/searchmanager.py
+diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
+index f75af03..314e4fd 100644
+--- a/app/backend/prepdocslib/searchmanager.py
++++ b/app/backend/prepdocslib/searchmanager.py
+@@ -103,7 +103,11 @@ class SearchManager:
+                         vector_search_dimensions=self.embedding_dimensions,
+                         vector_search_profile_name="embedding_config",
+                     ),
+-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
++                    SimpleField(
++                        name="category", 
++                        type="Edm.String", 
++                        filterable=True, 
++                        facetable=True),
+                     SimpleField(
+                         name="sourcepage",
+                         type="Edm.String",
+@@ -122,22 +126,18 @@ class SearchManager:
+                         filterable=True,
+                         facetable=False,
+                     ),
+-                ]
+-                if self.use_acls:
+-                    fields.append(
+-                        SimpleField(
+-                            name="oids",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
+-                    )
+-                    fields.append(
+-                        SimpleField(
+-                            name="groups",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
++                    SimpleField(
++                        name="oids",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
++                    ),
++                    SimpleField(
++                        name="groups",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
+                     )
++                ]
++                    
+                 if self.use_int_vectorization:
+                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
+                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
+#### scripts/generate_git_commit_message.py
+diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
+index 171fb03..00790e8 100644
+--- a/scripts/generate_git_commit_message.py
++++ b/scripts/generate_git_commit_message.py
+@@ -27,11 +27,11 @@ def get_file_diff(file_path):
+ 
+ def prepend_to_changelog(new_content):
+     changelog_path = "CHANGELOG.md"
+-    # if os.path.exists(changelog_path):
+-    #     with open(changelog_path, "r") as f:
+-    #         existing_content = f.read()
+-    # else:
+-    #     existing_content = ""
++    if os.path.exists(changelog_path):
++        with open(changelog_path, "r") as f:
++            existing_content = f.read()
++    else:
++        existing_content = ""
+ 
+     with open(changelog_path, "a") as f:
+         f.write(new_content + "\n\n")
+
+
#### app/backend/prepdocslib/searchmanager.py
diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
index f75af03..314e4fd 100644
--- a/app/backend/prepdocslib/searchmanager.py
+++ b/app/backend/prepdocslib/searchmanager.py
@@ -103,7 +103,11 @@ class SearchManager:
                         vector_search_dimensions=self.embedding_dimensions,
                         vector_search_profile_name="embedding_config",
                     ),
-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
+                    SimpleField(
+                        name="category", 
+                        type="Edm.String", 
+                        filterable=True, 
+                        facetable=True),
                     SimpleField(
                         name="sourcepage",
                         type="Edm.String",
@@ -122,22 +126,18 @@ class SearchManager:
                         filterable=True,
                         facetable=False,
                     ),
-                ]
-                if self.use_acls:
-                    fields.append(
-                        SimpleField(
-                            name="oids",
-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
-                            filterable=True,
-                        )
-                    )
-                    fields.append(
-                        SimpleField(
-                            name="groups",
-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
-                            filterable=True,
-                        )
+                    SimpleField(
+                        name="oids",
+                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+                        filterable=True,
+                    ),
+                    SimpleField(
+                        name="groups",
+                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+                        filterable=True,
                     )
+                ]
+                    
                 if self.use_int_vectorization:
                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
#### scripts/generate_git_commit_message.py
diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
index 171fb03..13254af 100644
--- a/scripts/generate_git_commit_message.py
+++ b/scripts/generate_git_commit_message.py
@@ -27,14 +27,14 @@ def get_file_diff(file_path):
 
 def prepend_to_changelog(new_content):
     changelog_path = "CHANGELOG.md"
-    # if os.path.exists(changelog_path):
-    #     with open(changelog_path, "r") as f:
-    #         existing_content = f.read()
-    # else:
-    #     existing_content = ""
+    if os.path.exists(changelog_path):
+        with open(changelog_path, "r") as f:
+            existing_content = f.read()
+    else:
+        existing_content = ""
 
-    with open(changelog_path, "a") as f:
-        f.write(new_content + "\n\n")
+    with open(changelog_path, "w") as f:
+        f.write(new_content + "\n\n" + existing_content)
 
 def main():
     repo_path = os.getcwd()


---
Generated on: 2025-02-24 13:46:12

### Changes made:

- .azure/pai-mm-prod/.env-temp
- CHANGELOG.md
- app/backend/prepdocslib/searchmanager.py
- scripts/generate_git_commit_message.py

### Detailed changes:

#### .azure/pai-mm-prod/.env-temp
diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
index adad91f..2983b9f 100644
--- a/.azure/pai-mm-prod/.env-temp
+++ b/.azure/pai-mm-prod/.env-temp
@@ -1,5 +1,4 @@
 AZURE_AUTH_TENANT_ID=""
-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
 AZURE_COSMOSDB_LOCATION="centralus"
 AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
 AZURE_ENFORCE_ACCESS_CONTROL="true"
#### CHANGELOG.md
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 4028629..0b174a3 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -1,3 +1,214 @@
+---
+Generated on: 2025-02-24 13:46:08
+
+### Changes made:
+
+- .azure/pai-mm-prod/.env-temp
+- CHANGELOG.md
+- app/backend/prepdocslib/searchmanager.py
+- scripts/generate_git_commit_message.py
+
+### Detailed changes:
+
+#### .azure/pai-mm-prod/.env-temp
+diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
+index adad91f..2983b9f 100644
+--- a/.azure/pai-mm-prod/.env-temp
++++ b/.azure/pai-mm-prod/.env-temp
+@@ -1,5 +1,4 @@
+ AZURE_AUTH_TENANT_ID=""
+-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
+ AZURE_COSMOSDB_LOCATION="centralus"
+ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
+ AZURE_ENFORCE_ACCESS_CONTROL="true"
+#### CHANGELOG.md
+diff --git a/CHANGELOG.md b/CHANGELOG.md
+index 4028629..e7e4c54 100644
+--- a/CHANGELOG.md
++++ b/CHANGELOG.md
+@@ -2151,3 +2151,101 @@ index dd2d488..44a233f 100644
+ \ No newline at end of file
+ 
+ 
++---
++Generated on: 2025-02-24 13:41:14
++
++### Changes made:
++
++- .azure/pai-mm-prod/.env-temp
++- app/backend/prepdocslib/searchmanager.py
++- scripts/generate_git_commit_message.py
++
++### Detailed changes:
++
++#### .azure/pai-mm-prod/.env-temp
++diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
++index adad91f..2983b9f 100644
++--- a/.azure/pai-mm-prod/.env-temp
+++++ b/.azure/pai-mm-prod/.env-temp
++@@ -1,5 +1,4 @@
++ AZURE_AUTH_TENANT_ID=""
++-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
++ AZURE_COSMOSDB_LOCATION="centralus"
++ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
++ AZURE_ENFORCE_ACCESS_CONTROL="true"
++#### app/backend/prepdocslib/searchmanager.py
++diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
++index f75af03..314e4fd 100644
++--- a/app/backend/prepdocslib/searchmanager.py
+++++ b/app/backend/prepdocslib/searchmanager.py
++@@ -103,7 +103,11 @@ class SearchManager:
++                         vector_search_dimensions=self.embedding_dimensions,
++                         vector_search_profile_name="embedding_config",
++                     ),
++-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
+++                    SimpleField(
+++                        name="category", 
+++                        type="Edm.String", 
+++                        filterable=True, 
+++                        facetable=True),
++                     SimpleField(
++                         name="sourcepage",
++                         type="Edm.String",
++@@ -122,22 +126,18 @@ class SearchManager:
++                         filterable=True,
++                         facetable=False,
++                     ),
++-                ]
++-                if self.use_acls:
++-                    fields.append(
++-                        SimpleField(
++-                            name="oids",
++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++-                            filterable=True,
++-                        )
++-                    )
++-                    fields.append(
++-                        SimpleField(
++-                            name="groups",
++-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++-                            filterable=True,
++-                        )
+++                    SimpleField(
+++                        name="oids",
+++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++                        filterable=True,
+++                    ),
+++                    SimpleField(
+++                        name="groups",
+++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+++                        filterable=True,
++                     )
+++                ]
+++                    
++                 if self.use_int_vectorization:
++                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
++                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
++#### scripts/generate_git_commit_message.py
++diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
++index 171fb03..00790e8 100644
++--- a/scripts/generate_git_commit_message.py
+++++ b/scripts/generate_git_commit_message.py
++@@ -27,11 +27,11 @@ def get_file_diff(file_path):
++ 
++ def prepend_to_changelog(new_content):
++     changelog_path = "CHANGELOG.md"
++-    # if os.path.exists(changelog_path):
++-    #     with open(changelog_path, "r") as f:
++-    #         existing_content = f.read()
++-    # else:
++-    #     existing_content = ""
+++    if os.path.exists(changelog_path):
+++        with open(changelog_path, "r") as f:
+++            existing_content = f.read()
+++    else:
+++        existing_content = ""
++ 
++     with open(changelog_path, "a") as f:
++         f.write(new_content + "\n\n")
++
++
+#### app/backend/prepdocslib/searchmanager.py
+diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
+index f75af03..314e4fd 100644
+--- a/app/backend/prepdocslib/searchmanager.py
++++ b/app/backend/prepdocslib/searchmanager.py
+@@ -103,7 +103,11 @@ class SearchManager:
+                         vector_search_dimensions=self.embedding_dimensions,
+                         vector_search_profile_name="embedding_config",
+                     ),
+-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
++                    SimpleField(
++                        name="category", 
++                        type="Edm.String", 
++                        filterable=True, 
++                        facetable=True),
+                     SimpleField(
+                         name="sourcepage",
+                         type="Edm.String",
+@@ -122,22 +126,18 @@ class SearchManager:
+                         filterable=True,
+                         facetable=False,
+                     ),
+-                ]
+-                if self.use_acls:
+-                    fields.append(
+-                        SimpleField(
+-                            name="oids",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
+-                    )
+-                    fields.append(
+-                        SimpleField(
+-                            name="groups",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
++                    SimpleField(
++                        name="oids",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
++                    ),
++                    SimpleField(
++                        name="groups",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
+                     )
++                ]
++                    
+                 if self.use_int_vectorization:
+                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
+                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
+#### scripts/generate_git_commit_message.py
+diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
+index 171fb03..13254af 100644
+--- a/scripts/generate_git_commit_message.py
++++ b/scripts/generate_git_commit_message.py
+@@ -27,14 +27,14 @@ def get_file_diff(file_path):
+ 
+ def prepend_to_changelog(new_content):
+     changelog_path = "CHANGELOG.md"
+-    # if os.path.exists(changelog_path):
+-    #     with open(changelog_path, "r") as f:
+-    #         existing_content = f.read()
+-    # else:
+-    #     existing_content = ""
++    if os.path.exists(changelog_path):
++        with open(changelog_path, "r") as f:
++            existing_content = f.read()
++    else:
++        existing_content = ""
+ 
+-    with open(changelog_path, "a") as f:
+-        f.write(new_content + "\n\n")
++    with open(changelog_path, "w") as f:
++        f.write(new_content + "\n\n" + existing_content)
+ 
+ def main():
+     repo_path = os.getcwd()
+
+
 ---
 Generated on: 2025-02-24 12:05:03
 
@@ -2151,3 +2362,101 @@ index dd2d488..44a233f 100644
 \ No newline at end of file
 
 
+---
+Generated on: 2025-02-24 13:41:14
+
+### Changes made:
+
+- .azure/pai-mm-prod/.env-temp
+- app/backend/prepdocslib/searchmanager.py
+- scripts/generate_git_commit_message.py
+
+### Detailed changes:
+
+#### .azure/pai-mm-prod/.env-temp
+diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
+index adad91f..2983b9f 100644
+--- a/.azure/pai-mm-prod/.env-temp
++++ b/.azure/pai-mm-prod/.env-temp
+@@ -1,5 +1,4 @@
+ AZURE_AUTH_TENANT_ID=""
+-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
+ AZURE_COSMOSDB_LOCATION="centralus"
+ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
+ AZURE_ENFORCE_ACCESS_CONTROL="true"
+#### app/backend/prepdocslib/searchmanager.py
+diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
+index f75af03..314e4fd 100644
+--- a/app/backend/prepdocslib/searchmanager.py
++++ b/app/backend/prepdocslib/searchmanager.py
+@@ -103,7 +103,11 @@ class SearchManager:
+                         vector_search_dimensions=self.embedding_dimensions,
+                         vector_search_profile_name="embedding_config",
+                     ),
+-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
++                    SimpleField(
++                        name="category", 
++                        type="Edm.String", 
++                        filterable=True, 
++                        facetable=True),
+                     SimpleField(
+                         name="sourcepage",
+                         type="Edm.String",
+@@ -122,22 +126,18 @@ class SearchManager:
+                         filterable=True,
+                         facetable=False,
+                     ),
+-                ]
+-                if self.use_acls:
+-                    fields.append(
+-                        SimpleField(
+-                            name="oids",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
+-                    )
+-                    fields.append(
+-                        SimpleField(
+-                            name="groups",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
++                    SimpleField(
++                        name="oids",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
++                    ),
++                    SimpleField(
++                        name="groups",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
+                     )
++                ]
++                    
+                 if self.use_int_vectorization:
+                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
+                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
+#### scripts/generate_git_commit_message.py
+diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
+index 171fb03..00790e8 100644
+--- a/scripts/generate_git_commit_message.py
++++ b/scripts/generate_git_commit_message.py
+@@ -27,11 +27,11 @@ def get_file_diff(file_path):
+ 
+ def prepend_to_changelog(new_content):
+     changelog_path = "CHANGELOG.md"
+-    # if os.path.exists(changelog_path):
+-    #     with open(changelog_path, "r") as f:
+-    #         existing_content = f.read()
+-    # else:
+-    #     existing_content = ""
++    if os.path.exists(changelog_path):
++        with open(changelog_path, "r") as f:
++            existing_content = f.read()
++    else:
++        existing_content = ""
+ 
+     with open(changelog_path, "a") as f:
+         f.write(new_content + "\n\n")
+
+
#### app/backend/prepdocslib/searchmanager.py
diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
index f75af03..314e4fd 100644
--- a/app/backend/prepdocslib/searchmanager.py
+++ b/app/backend/prepdocslib/searchmanager.py
@@ -103,7 +103,11 @@ class SearchManager:
                         vector_search_dimensions=self.embedding_dimensions,
                         vector_search_profile_name="embedding_config",
                     ),
-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
+                    SimpleField(
+                        name="category", 
+                        type="Edm.String", 
+                        filterable=True, 
+                        facetable=True),
                     SimpleField(
                         name="sourcepage",
                         type="Edm.String",
@@ -122,22 +126,18 @@ class SearchManager:
                         filterable=True,
                         facetable=False,
                     ),
-                ]
-                if self.use_acls:
-                    fields.append(
-                        SimpleField(
-                            name="oids",
-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
-                            filterable=True,
-                        )
-                    )
-                    fields.append(
-                        SimpleField(
-                            name="groups",
-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
-                            filterable=True,
-                        )
+                    SimpleField(
+                        name="oids",
+                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+                        filterable=True,
+                    ),
+                    SimpleField(
+                        name="groups",
+                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+                        filterable=True,
                     )
+                ]
+                    
                 if self.use_int_vectorization:
                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
#### scripts/generate_git_commit_message.py
diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
index 171fb03..13254af 100644
--- a/scripts/generate_git_commit_message.py
+++ b/scripts/generate_git_commit_message.py
@@ -27,14 +27,14 @@ def get_file_diff(file_path):
 
 def prepend_to_changelog(new_content):
     changelog_path = "CHANGELOG.md"
-    # if os.path.exists(changelog_path):
-    #     with open(changelog_path, "r") as f:
-    #         existing_content = f.read()
-    # else:
-    #     existing_content = ""
+    if os.path.exists(changelog_path):
+        with open(changelog_path, "r") as f:
+            existing_content = f.read()
+    else:
+        existing_content = ""
 
-    with open(changelog_path, "a") as f:
-        f.write(new_content + "\n\n")
+    with open(changelog_path, "w") as f:
+        f.write(new_content + "\n\n" + existing_content)
 
 def main():
     repo_path = os.getcwd()


---
Generated on: 2025-02-24 13:46:08

### Changes made:

- .azure/pai-mm-prod/.env-temp
- CHANGELOG.md
- app/backend/prepdocslib/searchmanager.py
- scripts/generate_git_commit_message.py

### Detailed changes:

#### .azure/pai-mm-prod/.env-temp
diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
index adad91f..2983b9f 100644
--- a/.azure/pai-mm-prod/.env-temp
+++ b/.azure/pai-mm-prod/.env-temp
@@ -1,5 +1,4 @@
 AZURE_AUTH_TENANT_ID=""
-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
 AZURE_COSMOSDB_LOCATION="centralus"
 AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
 AZURE_ENFORCE_ACCESS_CONTROL="true"
#### CHANGELOG.md
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 4028629..e7e4c54 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -2151,3 +2151,101 @@ index dd2d488..44a233f 100644
 \ No newline at end of file
 
 
+---
+Generated on: 2025-02-24 13:41:14
+
+### Changes made:
+
+- .azure/pai-mm-prod/.env-temp
+- app/backend/prepdocslib/searchmanager.py
+- scripts/generate_git_commit_message.py
+
+### Detailed changes:
+
+#### .azure/pai-mm-prod/.env-temp
+diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
+index adad91f..2983b9f 100644
+--- a/.azure/pai-mm-prod/.env-temp
++++ b/.azure/pai-mm-prod/.env-temp
+@@ -1,5 +1,4 @@
+ AZURE_AUTH_TENANT_ID=""
+-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
+ AZURE_COSMOSDB_LOCATION="centralus"
+ AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
+ AZURE_ENFORCE_ACCESS_CONTROL="true"
+#### app/backend/prepdocslib/searchmanager.py
+diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
+index f75af03..314e4fd 100644
+--- a/app/backend/prepdocslib/searchmanager.py
++++ b/app/backend/prepdocslib/searchmanager.py
+@@ -103,7 +103,11 @@ class SearchManager:
+                         vector_search_dimensions=self.embedding_dimensions,
+                         vector_search_profile_name="embedding_config",
+                     ),
+-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
++                    SimpleField(
++                        name="category", 
++                        type="Edm.String", 
++                        filterable=True, 
++                        facetable=True),
+                     SimpleField(
+                         name="sourcepage",
+                         type="Edm.String",
+@@ -122,22 +126,18 @@ class SearchManager:
+                         filterable=True,
+                         facetable=False,
+                     ),
+-                ]
+-                if self.use_acls:
+-                    fields.append(
+-                        SimpleField(
+-                            name="oids",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
+-                    )
+-                    fields.append(
+-                        SimpleField(
+-                            name="groups",
+-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+-                            filterable=True,
+-                        )
++                    SimpleField(
++                        name="oids",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
++                    ),
++                    SimpleField(
++                        name="groups",
++                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
++                        filterable=True,
+                     )
++                ]
++                    
+                 if self.use_int_vectorization:
+                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
+                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
+#### scripts/generate_git_commit_message.py
+diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
+index 171fb03..00790e8 100644
+--- a/scripts/generate_git_commit_message.py
++++ b/scripts/generate_git_commit_message.py
+@@ -27,11 +27,11 @@ def get_file_diff(file_path):
+ 
+ def prepend_to_changelog(new_content):
+     changelog_path = "CHANGELOG.md"
+-    # if os.path.exists(changelog_path):
+-    #     with open(changelog_path, "r") as f:
+-    #         existing_content = f.read()
+-    # else:
+-    #     existing_content = ""
++    if os.path.exists(changelog_path):
++        with open(changelog_path, "r") as f:
++            existing_content = f.read()
++    else:
++        existing_content = ""
+ 
+     with open(changelog_path, "a") as f:
+         f.write(new_content + "\n\n")
+
+
#### app/backend/prepdocslib/searchmanager.py
diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
index f75af03..314e4fd 100644
--- a/app/backend/prepdocslib/searchmanager.py
+++ b/app/backend/prepdocslib/searchmanager.py
@@ -103,7 +103,11 @@ class SearchManager:
                         vector_search_dimensions=self.embedding_dimensions,
                         vector_search_profile_name="embedding_config",
                     ),
-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
+                    SimpleField(
+                        name="category", 
+                        type="Edm.String", 
+                        filterable=True, 
+                        facetable=True),
                     SimpleField(
                         name="sourcepage",
                         type="Edm.String",
@@ -122,22 +126,18 @@ class SearchManager:
                         filterable=True,
                         facetable=False,
                     ),
-                ]
-                if self.use_acls:
-                    fields.append(
-                        SimpleField(
-                            name="oids",
-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
-                            filterable=True,
-                        )
-                    )
-                    fields.append(
-                        SimpleField(
-                            name="groups",
-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
-                            filterable=True,
-                        )
+                    SimpleField(
+                        name="oids",
+                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+                        filterable=True,
+                    ),
+                    SimpleField(
+                        name="groups",
+                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+                        filterable=True,
                     )
+                ]
+                    
                 if self.use_int_vectorization:
                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
#### scripts/generate_git_commit_message.py
diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
index 171fb03..13254af 100644
--- a/scripts/generate_git_commit_message.py
+++ b/scripts/generate_git_commit_message.py
@@ -27,14 +27,14 @@ def get_file_diff(file_path):
 
 def prepend_to_changelog(new_content):
     changelog_path = "CHANGELOG.md"
-    # if os.path.exists(changelog_path):
-    #     with open(changelog_path, "r") as f:
-    #         existing_content = f.read()
-    # else:
-    #     existing_content = ""
+    if os.path.exists(changelog_path):
+        with open(changelog_path, "r") as f:
+            existing_content = f.read()
+    else:
+        existing_content = ""
 
-    with open(changelog_path, "a") as f:
-        f.write(new_content + "\n\n")
+    with open(changelog_path, "w") as f:
+        f.write(new_content + "\n\n" + existing_content)
 
 def main():
     repo_path = os.getcwd()


---
Generated on: 2025-02-24 12:05:03

### Changes made:

- .gitignore
- .vscode/settings.json
- app/backend/app.py
- app/backend/approaches/prompts/chat_answer_question.prompty
- app/backend/approaches/prompts/chat_query_rewrite.prompty
- app/backend/approaches/prompts/chat_query_rewrite_tools.json
- app/backend/core/authentication.py
- app/frontend/index.html
- app/frontend/public/favicon.ico
- app/frontend/src/components/AnalysisPanel/AnalysisPanel.tsx
- app/frontend/src/components/Answer/Answer.tsx
- app/frontend/src/components/Answer/AnswerError.tsx
- app/frontend/src/components/Answer/AnswerIcon.tsx
- app/frontend/src/components/Example/Example.module.css
- app/frontend/src/components/LoginButton/LoginButton.module.css
- app/frontend/src/locales/en/translation.json
- app/frontend/src/pages/chat/Chat.module.css
- app/frontend/src/pages/chat/Chat.tsx
- app/frontend/src/pages/layout/Layout.module.css
- app/frontend/src/pages/layout/Layout.tsx
- infra/core/storage/storage-account.bicep
- infra/main.bicep
- scripts/sampleacls.json

### Detailed changes:

#### .gitignore
diff --git a/.gitignore b/.gitignore
index 8509e7a..9093a11 100644
--- a/.gitignore
+++ b/.gitignore
@@ -1,5 +1,4 @@
 # Azure az webapp deployment details
-.azure
 *_env
 data/
 
#### .vscode/settings.json
diff --git a/.vscode/settings.json b/.vscode/settings.json
index aae6b8d..43d3664 100644
--- a/.vscode/settings.json
+++ b/.vscode/settings.json
@@ -30,5 +30,22 @@
         "tests"
     ],
     "python.testing.unittestEnabled": false,
-    "python.testing.pytestEnabled": true
+    "python.testing.pytestEnabled": true,
+    "prompty.modelConfigurations": [
+        {
+            "name": "default",
+            "type": "azure_openai",
+            "api_version": "2024-08-01-preview",
+            "azure_endpoint": "https://entelligage-azure-openai.openai.azure.com/",
+            "azure_deployment": "eg-gpt-4o",
+            "api_key": ""
+        },
+        {
+            "name": "gpt-3.5-turbo",
+            "type": "openai",
+            "api_key": "${env:OPENAI_API_KEY}",
+            "organization": "${env:OPENAI_ORG_ID}",
+            "base_url": "${env:OPENAI_BASE_URL}"
+        }
+    ]
 }
#### app/backend/app.py
diff --git a/app/backend/app.py b/app/backend/app.py
index c364c89..913ab90 100644
--- a/app/backend/app.py
+++ b/app/backend/app.py
@@ -446,8 +446,7 @@ async def setup_clients():
     AZURE_SERVER_APP_SECRET = os.getenv("AZURE_SERVER_APP_SECRET")
     AZURE_CLIENT_APP_ID = os.getenv("AZURE_CLIENT_APP_ID")
     AZURE_AUTH_TENANT_ID = os.getenv("AZURE_AUTH_TENANT_ID", AZURE_TENANT_ID)
-    AZURE_AUTH_TENANT_NAME = os.getenv("AZURE_AUTH_TENANT_NAME")
-
+    
     KB_FIELDS_CONTENT = os.getenv("KB_FIELDS_CONTENT", "content")
     KB_FIELDS_SOURCEPAGE = os.getenv("KB_FIELDS_SOURCEPAGE", "sourcepage")
 
@@ -527,7 +526,6 @@ async def setup_clients():
         server_app_secret=AZURE_SERVER_APP_SECRET,
         client_app_id=AZURE_CLIENT_APP_ID,
         tenant_id=AZURE_AUTH_TENANT_ID,
-        tenant_name=AZURE_AUTH_TENANT_NAME,
         require_access_control=AZURE_ENFORCE_ACCESS_CONTROL,
         enable_global_documents=AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS,
         enable_unauthenticated_access=AZURE_ENABLE_UNAUTHENTICATED_ACCESS,
#### app/backend/approaches/prompts/chat_answer_question.prompty
diff --git a/app/backend/approaches/prompts/chat_answer_question.prompty b/app/backend/approaches/prompts/chat_answer_question.prompty
index 3dcb05a..434701a 100644
--- a/app/backend/approaches/prompts/chat_answer_question.prompty
+++ b/app/backend/approaches/prompts/chat_answer_question.prompty
@@ -1,40 +1,113 @@
 ---
-name: Chat
+name: MM Chat Prompt
 description: Answer a question (with chat history) using solely text sources.
 model:
     api: chat
 sample:
-    user_query: What does a product manager do that a CEO doesn't?
+    user_query: What is the purpose of the Whistleblower Policy?
     include_follow_up_questions: true
     past_messages:
         - role: user
-          content: "What does a CEO do?"
+          content: "What is a whistleblower?"
         - role: assistant
-          content: "A CEO, or Chief Executive Officer, is responsible for providing strategic direction and oversight to a company to ensure its long-term success and profitability. They develop and implement strategies and objectives for financial success and growth, provide guidance to the executive team, manage day-to-day operations, ensure compliance with laws and regulations, develop and maintain relationships with stakeholders, monitor industry trends, and represent the company in public events 12. [role_library.pdf#page=1][role_library.pdf#page=3]"
+          content: "A whistleblower is an individual—typically an employee, director, volunteer, or other stakeholder—who reports unethical, illegal, or improper activities within an organization. Based on the context provided from the Whistleblower Policy, a whistleblower specifically raises concerns about: Questionable Accounting or Audit Matters – Issues related to financial reporting, fraud, mismanagement of funds, or violations of financial regulations. Violations of Ethics, Fraud, or Predatory Lending Policies – Any unethical or fraudulent behavior that breaches company policies or legal standards.Internal Controls & Compliance Violations – Problems in business operations that may compromise the organization's integrity."
     text_sources:
-        - "role_library.pdf#page=29:  The Manager of Product Management will collaborate with internal teams, such as engineering, sales, marketing, and finance, as well as external partners, suppliers, and customers to ensure successful product execution. Responsibilities: · Lead the product management team and provide guidance on product strategy, design, development, and launch. · Develop and implement product life-cycle management processes. · Monitor and analyze industry trends to identify opportunities for new products. · Develop product marketing plans and go-to-market strategies. · Research customer needs and develop customer-centric product roadmaps. · Collaborate with internal teams to ensure product execution and successful launch. · Develop pricing strategies and cost models. · Oversee product portfolio and performance metrics. · Manage product development budget. · Analyze product performance and customer feedback to identify areas for improvement. Qualifications: · Bachelor's degree in business, engineering, or a related field. · At least 5 years of experience in product management. · Proven track record of successful product launches."
-        - "role_library.pdf#page=23: Company: Contoso Electronics Location: Anywhere Job Type: Full-Time Salary: Competitive, commensurate with experience Job Summary: The Senior Manager of Product Management will be responsible for leading the product management team at Contoso Electronics. This role includes developing strategies, plans and objectives for the product management team and managing the day-to-day operations. The Senior Manager of Product Management will be responsible for the successful launch of new products and the optimization of existing products. Responsibilities: · Develop and implement product management strategies, plans and objectives to maximize team performance. · Analyze competitive landscape and market trends to develop product strategies. · Lead the product management team in the development of product plans, roadmaps and launch plans. · Monitor the performance of product management team, analyze results and implement corrective action as needed. · Manage the product lifecycle, including product development, launch, and end of life. · Ensure product features and benefits meet customer requirements. · Establish and maintain relationships with key customers, partners, and vendors."
-        - "role_library.pdf#page=28:  · 7+ years of experience in research and development in the electronics sector. · Proven track record of successfully designing, testing, and optimizing products. · Experience leading a team of researchers and engineers. · Excellent problem-solving and analytical skills. · Ability to work in a fast-paced environment and meet tight deadlines.· Knowledge of industry trends, technologies, and regulations. · Excellent communication and presentation skills. Manager of Product Management Job Title: Manager of Product Management, Contoso Electronics Job Summary: The Manager of Product Management is responsible for overseeing the product management team, driving product development and marketing strategy for Contoso Electronics. This individual will be accountable for the successful launch of new products and the implementation of product life-cycle management processes. The Manager of Product Management will collaborate with internal teams, such as engineering, sales, marketing, and finance, as well as external partners, suppliers, and customers to ensure successful product execution."
+        - "3-84 Whistleblower Policy.pdf#page=1:  3-84 - Whistleblower Policy\nGeneral\nWe require employees to observe high standards of business and personal ethics in the conduct of their duties and responsibilities. The objectives of the Whistleblower Policy are to establish policies and procedures for:\n· The submission of concerns regarding questionable accounting or audit matters by employees, directors, officers, and other stakeholders of the organization, on a confidential and anonymous basis.\n· The receipt, retention, and treatment of complaints received by the organization regarding accounting, internal controls, or auditing matters.\n· The protection of directors, volunteers and employees reporting concerns from retaliatory actions.\nReporting Responsibility\nEach director, volunteer, and employee of Company Name has an obligation to report in accordance with this Whistleblower Policy (a) questionable or improper accounting or auditing matters, and (b) violations and suspected violations of Company Name's Ethics, Fraud or Predatory Lending Policy (hereinafter collectively referred to as Concerns)."
+        - "3-84 Whistleblower Policy.pdf#page=1: in accordance with this Whistleblower Policy (a) questionable or improper accounting or auditing matters, and (b) violations and suspected violations of Company Name's Ethics, Fraud or Predatory Lending Policy (hereinafter collectively referred to as Concerns).\nAuthority of Audit Committee\nAll reported Concerns will be forwarded to the Quality Control Auditor in accordance with the procedures set forth herein. The Quality Control Auditor shall be responsible for investigating, and making appropriate recommendations to the Board of Directors, with respect to all reported Concerns.\nNo RetaliationThis Whistleblower Policy is intended to encourage and enable directors, volunteers, and employees to raise Concerns within the Organization for investigation and appropriate action. With this goal in mind, no director, volunteer, or employee who, in good faith, reports a Concern shall be subject to retaliation or, in the case of an employee, adverse employment consequences. Moreover, a volunteer or employee who retaliates against someone who has reported a Concern in good faith is subject to discipline up to and including dismissal from the volunteer position or termination of employment."
+        - "2-0 Compliance Policies and Procedures.pdf#page=271: Documentation of Error</td><td>Y\n:selected:</td><td>N\n:selected:</td></tr></table></figure>\n\n\n\nDescription of Complaint\nComplaint Resolution\nFORM 2-70 COMP OPS ORIG Complaint Resolution\nPage 271Insert_Logo_Here\nCompany Name Regulatory Compliance\n3-84 - Whistleblower Policy\nGeneral\nWe require employees to observe high standards of business and personal ethics in the conduct of their duties and responsibilities. The objectives of the Whistleblower Policy are to establish policies and procedures for:\n· The submission of concerns regarding questionable accounting or audit matters by employees, directors, officers, and other stakeholders of the organization, on a confidential and anonymous basis.\n· The receipt, retention, and treatment of complaints received by the organization regarding accounting, internal controls, or auditing matters.\n· The protection of directors, volunteers and employees reporting concerns from retaliatory actions.\nReporting Responsibility\nEach director, volunteer, and employee of Company Name has an obligation to report in accordance with this Whistleblower Policy (a) questionable or improper accounting or auditing matters, and (b) violations and "
 ---
 system:
 {% if override_prompt %}
 {{ override_prompt }}
 {% else %}
-Assistant helps the company employees with their healthcare plan questions, and questions about the employee handbook. Be brief in your answers.
-Answer ONLY with the facts listed in the list of sources below. If there isn't enough information below, say you don't know. Do not generate answers that don't use the sources below. If asking a clarifying question to the user would help, ask the question.
-If the question is not in English, answer in the language used in the question.
-Each source has a name followed by colon and the actual information, always include the source name for each fact you use in the response. Use square brackets to reference the source, for example [info1.txt]. Don't combine sources, list each source separately, for example [info1.txt][info2.pdf].
+You are a highly intelligent and resourceful assistant designed to serve as a compliance specialist for a mortgage company, responding to employee inquiries as if they come from mortgage loan specialists. Your primary function is to provide employees with excerpts from the company’s policies and procedures regarding mortgage processes, policies, laws, and guidelines. Additionally, you must include the document name and page number where the information was sourced, enabling employees to locate the references for further clarification. Your responses should be actionable, ensuring mortgage specialists understand how to comply with the policies provided.
+
+### Objectives
+1. Serve as a compliance specialist for a mortgage company, responding to employee inquiries as if they come from mortgage loan specialists.
+2. Provide clear, actionable responses based on the company’s policies and procedures to help mortgage professionals ensure compliance and minimize errors.
+3. Adapt response format dynamically: If a clear direct quote exists, start with it. Otherwise, provide a summarized response first, followed by relevant supporting quotes.
+4. Offer proactive compliance insights: Identify potential audit risks and provide best practices to mitigate issues.
+5. Assist in problem-solving and efficiency: Suggest alternative solutions, workflow optimizations, and compliance checklists to help employees successfully close loans while following regulations.
+6. If an answer cannot be determined with the provided context, explicitly state this and guide employees toward escalation or additional resources.
+
+### Guidelines
+1. **Proactive Compliance Alerts**: If an inquiry suggests a potential violation or audit risk, provide a proactive warning with mitigation steps.
+2. **Alternative Solutions & Workarounds**: Offer practical alternatives if policies allow flexibility, ensuring successful loan closures.
+3. **Operational Efficiency Tips**: Suggest workflow optimizations to streamline compliance.
+4. **User-Centric Formatting**: Use bullet points and numbered lists to break down complex policies into actionable steps.
+5. **Direct Quotes**: If a clear and concise direct quote exists, start with it. If multiple policies apply or a quote is unclear, begin with a summary, followed by supporting quotes.
+7. **Summarization**: Summarize the response in a user-friendly way. When applicable, follow with supporting excerpts.
+8. **Clarity**: Ensure the response is clear, concise, and actionable, guiding the employee to understand and implement the provided guidance.
+9. **Acknowledgment of Gaps**: If no answer can be determined with the context, state this transparently.
+
+### Process
+
+0. **Acknowledgment the Inquiry**: Start by acknowledging the user's question to provide context for the response.
+1. **Interactive Troubleshooting Path**: Guide users through decision-tree-based solutions for more complex compliance challenges.
+2. **Escalation & Expert Consultation**: If a question requires company-specific ruling, suggest escalation to compliance officers.
+3. **Audit Risk Awareness**: Highlight frequent audit issues related to the inquiry and recommend best practices to mitigate risk.
+4. **Customizable Compliance Checklists**: Provide dynamic checklists to help employees self-validate compliance before submission.
+5. **Search Context**: Use the provided documents (with filenames and page numbers) to locate the most relevant excerpts.
+6. **Provide Excerpts**: Share the most relevant excerpt(s) from the document(s). If needed, provide a summarized response first before citing excerpts.
+7. **Summarize with Actionable Guidance**: Briefly summarize the provided information, explaining how the employee should act on it.
+8. **Cite References**: Each source has a name followed by colon and the actual information, always include the source name for each fact you use in the response. Use square brackets to reference the source, for example [info1.txt]. Don't combine sources, list each source separately, for example [info1.txt][info2.pdf].
+9. **Follow-up Questions**: - Do NOT include a header or heading for "Follow-Up Questions".
+
+### Examples
+
+**Example Inquiry 1**
+- *Inquiry*: "What are the guidelines for documenting a borrower’s income?"
+
+**Response**:
+
+- *Direct Quote*: "Income documentation must include a written verification of employment (VOE) and at least two recent pay stubs. Self-employed borrowers must provide two years of personal and business tax returns."
+[MortgageUnderwritingGuidelines.pdf#page=15]
+
+- *Summary*: You must verify borrower income through proper documentation. Ensure employed borrowers provide a written verification of employment and recent pay stubs, while self-employed borrowers submit tax returns from the past two years.
+
+**Example Inquiry 2**
+- *Inquiry*: "What is the process for reporting suspected fraud?"
+
+**Response**:
+
+- *Direct Quote*: "All instances of suspected fraud must be reported to the Compliance Department within 24 hours. Use the Incident Reporting Form found in the Appendix to document details of the suspected fraud."
+[FraudPreventionPlan.pdf#page=9]
+
+- *Direct Quote*: "Employees may also report suspected fraud anonymously through the company’s whistleblower hotline."
+[ComplianceManagementSystem.pdf#page=22]
+
+- *Summary*: If you suspect fraud, report it to the Compliance Department within 24 hours using the Incident Reporting Form. Alternatively, you can use the anonymous whistleblower hotline.
+
+**Example Inquiry 3**
+- *Inquiry*: "What is our policy on loan file retention?"
+
+**Response**:
+
+- *Direct Quote*: "Loan files must be retained for a minimum of five years after the loan closing date, as per federal and state regulations."
+[DocumentRetentionPolicy.pdf#page=7]
+
+- *Summary*: You are required to retain all loan files for at least five years post-closing, as mandated by federal and state laws. Ensure both digital and physical copies are securely stored in compliance with document retention procedures.
+
+{injected_prompt}
+
+
 {{ injected_prompt }}
 {% endif %}
 
 {% if include_follow_up_questions %}
-Generate 3 very brief follow-up questions that the user would likely ask next.
-Enclose the follow-up questions in double angle brackets. Example:
-<<Are there exclusions for prescriptions?>>
-<<Which pharmacies can be ordered from?>>
-<<What is the limit for over-the-counter medication?>>
-Do not repeat questions that have already been asked.
-Make sure the last question ends with ">>".
+Generate 3 concise and relevant follow-up questions that a user might ask next about mortgage policies and procedures. 
+
+**Guidelines:**
+- Ensure questions build upon the original inquiry, offering deeper insights or clarifications.
+- Use double angle brackets to enclose the questions.
+- Do not repeating previously asked questions.
+- Do not include a header or heading for "Follow Up Questions".
+- The last question must always end with ">>".
+
+**Example:**
+<<Can you clarify the timeline for compliance reviews?>>
+<<What alternative documentation can be used in special cases?>>
+<<How should discrepancies in verification be handled?>>
 {% endif %}
 
 {% for message in past_messages %}
#### app/backend/approaches/prompts/chat_query_rewrite.prompty
diff --git a/app/backend/approaches/prompts/chat_query_rewrite.prompty b/app/backend/approaches/prompts/chat_query_rewrite.prompty
index 7738a85..55f9dee 100644
--- a/app/backend/approaches/prompts/chat_query_rewrite.prompty
+++ b/app/backend/approaches/prompts/chat_query_rewrite.prompty
@@ -6,12 +6,12 @@ model:
     parameters:
         tools: ${file:chat_query_rewrite_tools.json}
 sample:
-    user_query: Does it include hearing?
+    user_query: Does it include FHA guidelines?
     past_messages:
         - role: user
-          content: "What is included in my Northwind Health Plus plan that is not in standard?"
+          content: "What is included in the Mortgage Compliance Manual that is not in the Standard Policies Manual?"
         - role: assistant
-          content: "The Northwind Health Plus plan includes coverage for emergency services, mental health and substance abuse coverage, and out-of-network services, which are not included in the Northwind Standard plan. [Benefit_Options.pdf#page=3]"
+          content: "The Mortgage Compliance Manual includes detailed guidelines on fair lending practices, anti-money laundering (AML) requirements, and regulatory reporting, which are not included in the Standard Policies Manual. [Compliance_Manual.pdf#page=5]"
 ---
 system:
 Below is a history of the conversation so far, and a new question asked by the user that needs to be answered by searching in a knowledge base.
@@ -24,16 +24,16 @@ If the question is not in English, translate the question to English before gene
 If you cannot generate a search query, return just the number 0.
 
 user:
-(EXAMPLE) How did crypto do last year?
+(EXAMPLE) How did mortgage rates change last year?
 
 assistant:
-Summarize Cryptocurrency Market Dynamics from last year
+Summarize Mortgage Rate Trends from last year
 
 user:
-(EXAMPLE) What are my health plans?
+(EXAMPLE) What mortgage manuals are available?
 
 assistant:
-Show available health plans
+Show available mortgage manuals
 
 {% for message in past_messages %}
 {{ message["role"] }}:
#### app/backend/approaches/prompts/chat_query_rewrite_tools.json
diff --git a/app/backend/approaches/prompts/chat_query_rewrite_tools.json b/app/backend/approaches/prompts/chat_query_rewrite_tools.json
index cf17434..9250404 100644
--- a/app/backend/approaches/prompts/chat_query_rewrite_tools.json
+++ b/app/backend/approaches/prompts/chat_query_rewrite_tools.json
@@ -8,7 +8,7 @@
             "properties": {
                 "search_query": {
                     "type": "string",
-                    "description": "Query string to retrieve documents from azure search eg: 'Health care plan'"
+                    "description": "Query string to retrieve documents from azure search eg: 'Whistleblower policy'"
                 }
             },
             "required": ["search_query"]
#### app/backend/core/authentication.py
diff --git a/app/backend/core/authentication.py b/app/backend/core/authentication.py
index 531035e..0c563e0 100644
--- a/app/backend/core/authentication.py
+++ b/app/backend/core/authentication.py
@@ -1,5 +1,6 @@
 # Refactored from https://github.com/Azure-Samples/ms-identity-python-on-behalf-of
-
+import ssl
+import certifi
 import base64
 import json
 import logging
@@ -42,7 +43,6 @@ class AuthenticationHelper:
         server_app_secret: Optional[str],
         client_app_id: Optional[str],
         tenant_id: Optional[str],
-        tenant_name: Optional[str],
         require_access_control: bool = False,
         enable_global_documents: bool = False,
         enable_unauthenticated_access: bool = False,
@@ -52,15 +52,12 @@ class AuthenticationHelper:
         self.server_app_secret = server_app_secret
         self.client_app_id = client_app_id
         self.tenant_id = tenant_id
-        self.authority = f"https://{tenant_name}.ciamlogin.com/{tenant_id}" if tenant_name else f"https://login.microsoftonline.com/{tenant_id}"
+        self.authority = f"https://{tenant_id}.ciamlogin.com/{tenant_id}" 
         # Depending on if requestedAccessTokenVersion is 1 or 2, the issuer and audience of the token may be different
         # See https://learn.microsoft.com/graph/api/resources/apiapplication
         self.valid_issuers = [
-            f"https://sts.windows.net/{tenant_id}/",
-            f"https://login.microsoftonline.com/{tenant_id}/v2.0",
+            f"https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0",
         ]
-        if tenant_name:
-            self.valid_issuers.append(f"https://{tenant_name}.ciamlogin.com/{tenant_id}/v2.0")
         self.valid_audiences = [f"api://{server_app_id}", str(server_app_id)]
         # See https://learn.microsoft.com/entra/identity-platform/access-tokens#validate-the-issuer for more information on token validation
         self.key_url = f"{self.authority}/discovery/v2.0/keys"
@@ -183,9 +180,11 @@ class AuthenticationHelper:
 
     @staticmethod
     async def list_groups(graph_resource_access_token: dict) -> list[str]:
+        ssl_context = ssl.create_default_context(cafile=certifi.where())
+        conn = aiohttp.TCPConnector(ssl=ssl_context)
         headers = {"Authorization": "Bearer " + graph_resource_access_token["access_token"]}
         groups = []
-        async with aiohttp.ClientSession(headers=headers) as session:
+        async with aiohttp.ClientSession(headers=headers,connector=conn) as session:
             resp_json = None
             resp_status = None
             async with session.get(url="https://graph.microsoft.com/v1.0/me/transitiveMemberOf?$select=id") as resp:
@@ -310,6 +309,8 @@ class AuthenticationHelper:
         """
         Validate an access token is issued by Entra
         """
+        ssl_context = ssl.create_default_context(cafile=certifi.where())
+        conn = aiohttp.TCPConnector(ssl=ssl_context)
         jwks = None
         async for attempt in AsyncRetrying(
             retry=retry_if_exception_type(AuthError),
@@ -317,7 +318,7 @@ class AuthenticationHelper:
             stop=stop_after_attempt(5),
         ):
             with attempt:
-                async with aiohttp.ClientSession() as session:
+                async with aiohttp.ClientSession(connector=conn) as session:
                     async with session.get(url=self.key_url) as resp:
                         resp_status = resp.status
                         if resp_status in [500, 502, 503, 504]:
#### app/frontend/index.html
diff --git a/app/frontend/index.html b/app/frontend/index.html
index 30205db..9e06dfb 100644
--- a/app/frontend/index.html
+++ b/app/frontend/index.html
@@ -2,9 +2,10 @@
 <html lang="en">
     <head>
         <meta charset="UTF-8" />
-        <link rel="icon" type="image/x-icon" href="/favicon.ico" />
+        <link rel="icon" type="image/x-icon" href="https://stjeegpqns5eeds.blob.core.windows.net/assets/favicon.ico" />
+        <link rel="apple-touch-icon" href="https://stjeegpqns5eeds.blob.core.windows.net/assets/apple-touch-icon.png" />
         <meta name="viewport" content="width=device-width, initial-scale=1.0" />
-        <title>Azure OpenAI + AI Search</title>
+        <title>Mortgage Manuals PrismAI</title>
     </head>
     <body>
         <div id="root"></div>
#### app/frontend/public/favicon.ico
diff --git a/app/frontend/public/favicon.ico b/app/frontend/public/favicon.ico
index f1fe505..9753e43 100644
Binary files a/app/frontend/public/favicon.ico and b/app/frontend/public/favicon.ico differ
#### app/frontend/src/components/AnalysisPanel/AnalysisPanel.tsx
diff --git a/app/frontend/src/components/AnalysisPanel/AnalysisPanel.tsx b/app/frontend/src/components/AnalysisPanel/AnalysisPanel.tsx
index 2cee00c..8703754 100644
--- a/app/frontend/src/components/AnalysisPanel/AnalysisPanel.tsx
+++ b/app/frontend/src/components/AnalysisPanel/AnalysisPanel.tsx
@@ -77,13 +77,13 @@ export const AnalysisPanel = ({ answer, activeTab, activeCitation, citationHeigh
             selectedKey={activeTab}
             onLinkClick={pivotItem => pivotItem && onActiveTabChanged(pivotItem.props.itemKey! as AnalysisPanelTabs)}
         >
-            <PivotItem
+            {/* <PivotItem
                 itemKey={AnalysisPanelTabs.ThoughtProcessTab}
                 headerText={t("headerTexts.thoughtProcess")}
                 headerButtonProps={isDisabledThoughtProcessTab ? pivotItemDisabledStyle : undefined}
             >
                 <ThoughtProcess thoughts={answer.context.thoughts || []} />
-            </PivotItem>
+            </PivotItem> */}
             <PivotItem
                 itemKey={AnalysisPanelTabs.SupportingContentTab}
                 headerText={t("headerTexts.supportingContent")}
#### app/frontend/src/components/Answer/Answer.tsx
diff --git a/app/frontend/src/components/Answer/Answer.tsx b/app/frontend/src/components/Answer/Answer.tsx
index 75b0a03..9edceef 100644
--- a/app/frontend/src/components/Answer/Answer.tsx
+++ b/app/frontend/src/components/Answer/Answer.tsx
@@ -74,14 +74,14 @@ export const Answer = ({
                             ariaLabel={copied ? t("tooltips.copied") : t("tooltips.copy")}
                             onClick={handleCopy}
                         />
-                        <IconButton
+                        {/* <IconButton
                             style={{ color: "black" }}
                             iconProps={{ iconName: "Lightbulb" }}
                             title={t("tooltips.showThoughtProcess")}
                             ariaLabel={t("tooltips.showThoughtProcess")}
                             onClick={() => onThoughtProcessClicked()}
                             disabled={!answer.context.thoughts?.length}
-                        />
+                        /> */}
                         <IconButton
                             style={{ color: "black" }}
                             iconProps={{ iconName: "ClipboardList" }}
#### app/frontend/src/components/Answer/AnswerError.tsx
diff --git a/app/frontend/src/components/Answer/AnswerError.tsx b/app/frontend/src/components/Answer/AnswerError.tsx
index 49d3d2d..f871cea 100644
--- a/app/frontend/src/components/Answer/AnswerError.tsx
+++ b/app/frontend/src/components/Answer/AnswerError.tsx
@@ -9,12 +9,13 @@ interface Props {
 }
 
 export const AnswerError = ({ error, onRetry }: Props) => {
+    const errorMessage = error.includes("Request failed with status 403") ? "Please login to continue..." : error;
     return (
         <Stack className={styles.answerContainer} verticalAlign="space-between">
             <ErrorCircle24Regular aria-hidden="true" aria-label="Error icon" primaryFill="red" />
 
             <Stack.Item grow>
-                <p className={styles.answerText}>{error}</p>
+                <p className={styles.answerText}>{errorMessage}</p>
             </Stack.Item>
 
             <PrimaryButton className={styles.retryButton} onClick={onRetry} text="Retry" />
#### app/frontend/src/components/Answer/AnswerIcon.tsx
diff --git a/app/frontend/src/components/Answer/AnswerIcon.tsx b/app/frontend/src/components/Answer/AnswerIcon.tsx
index 9ddbc48..136922c 100644
--- a/app/frontend/src/components/Answer/AnswerIcon.tsx
+++ b/app/frontend/src/components/Answer/AnswerIcon.tsx
@@ -1,5 +1,8 @@
 import { Sparkle28Filled } from "@fluentui/react-icons";
 
 export const AnswerIcon = () => {
-    return <Sparkle28Filled primaryFill={"rgba(115, 118, 225, 1)"} aria-hidden="true" aria-label="Answer logo" />;
+    const imageUrl = "https://stjeegpqns5eeds.blob.core.windows.net/assets/apple-touch-icon.png";
+    return <img src={imageUrl} alt="Answer logo" aria-hidden="true" aria-label="Answer logo" style={{ width: "28px", height: "28px" }} />;
+
+    // return <Sparkle28Filled primaryFill={"rgba(115, 118, 225, 1)"} aria-hidden="true" aria-label="Answer logo" />;
 };
#### app/frontend/src/components/Example/Example.module.css
diff --git a/app/frontend/src/components/Example/Example.module.css b/app/frontend/src/components/Example/Example.module.css
index 1b1471c..0ab3f10 100644
--- a/app/frontend/src/components/Example/Example.module.css
+++ b/app/frontend/src/components/Example/Example.module.css
@@ -30,7 +30,7 @@
     margin: 0;
     font-size: 1.25rem;
     width: 25rem;
-    padding: 0.5rem;
+    padding: 1rem;
     min-height: 4.5rem;
 }
 
#### app/frontend/src/components/LoginButton/LoginButton.module.css
diff --git a/app/frontend/src/components/LoginButton/LoginButton.module.css b/app/frontend/src/components/LoginButton/LoginButton.module.css
index 1a36829..d2222b3 100644
--- a/app/frontend/src/components/LoginButton/LoginButton.module.css
+++ b/app/frontend/src/components/LoginButton/LoginButton.module.css
@@ -1,6 +1,10 @@
 .loginButton {
     border-radius: 0.3125em;
     font-weight: 100;
+    font-size: 1rem;
     margin: 0;
-    padding: 0.5rem 1rem;
+    padding-left: 0.25rem;
+    padding-right: 0.25rem;
+    padding-top: 0.25rem;
+    padding-bottom: 0.5rem;
 }
#### app/frontend/src/locales/en/translation.json
diff --git a/app/frontend/src/locales/en/translation.json b/app/frontend/src/locales/en/translation.json
index 07f657d..094fc22 100644
--- a/app/frontend/src/locales/en/translation.json
+++ b/app/frontend/src/locales/en/translation.json
@@ -1,7 +1,7 @@
 {
-    "pageTitle": "Azure OpenAI + AI Search",
-    "headerTitle": "Azure OpenAI + AI Search",
-    "chat": "Chat",
+    "pageTitle": "Mortgage Manuals PrismAI",
+    "headerTitle": "Mortgage Manuals PrismAI",
+    "chat": "Policy Assistant",
     "qa": "Ask a question",
     "login": "Login",
     "logout": "Logout",
@@ -34,20 +34,20 @@
     },
     "developerSettings": "Developer settings",
 
-    "chatEmptyStateTitle": "Chat with your data",
-    "chatEmptyStateSubtitle": "Ask anything or try an example",
+    "chatEmptyStateTitle": "Your Mortgage Process Assistant",
+    "chatEmptyStateSubtitle": "Ask anything about your mortgage policies and procedures.",
     "defaultExamples": {
-        "1": "What is included in my Northwind Health Plus plan that is not in standard?",
-        "2": "What happens in a performance review?",
-        "3": "What does a Product Manager do?",
-        "placeholder": "Type a new question (e.g. does my plan cover annual eye exams?)"
+        "1": "How many days do I have to send out an LE?",
+        "2": "What are the FHA underwriting guidelines?",
+        "3": "What are the key requirements for a Quality Control Plan?",
+        "placeholder": "Type a new question (e.g., What are the RESPA disclosure requirements?)"
     },
-    "askTitle": "Ask your data",
+    "askTitle": "Ask about Mortgage Compliance",
     "gpt4vExamples": {
-        "1": "Compare the impact of interest rates and GDP in financial markets.",
-        "2": "What is the expected trend for the S&P 500 index over the next five years? Compare it to the past S&P 500 performance",
-        "3": "Can you identify any correlation between oil prices and stock market trends?",
-        "placeholder": "Example: Does my plan cover annual eye exams?"
+        "1": "Compare the impact of interest rate changes on mortgage origination and loan default rates.",
+        "2": "What are the current FHA and Fannie Mae loan limits for different regions?",
+        "3": "Can you identify any trends in mortgage fraud detection over the past five years?",
+        "placeholder": "Example: What are the TRID disclosure timing requirements?"
     },
     "generatingAnswer": "Generating answer",
     "citationWithColon": "Citation:",
#### app/frontend/src/pages/chat/Chat.module.css
diff --git a/app/frontend/src/pages/chat/Chat.module.css b/app/frontend/src/pages/chat/Chat.module.css
index 4534852..8ee0840 100644
--- a/app/frontend/src/pages/chat/Chat.module.css
+++ b/app/frontend/src/pages/chat/Chat.module.css
@@ -30,15 +30,19 @@
 }
 
 .chatEmptyStateTitle {
-    font-size: 2.75rem;
+    font-size: 1.75rem;
     font-weight: 600;
-    margin-top: 0;
-    margin-bottom: 1.875rem;
+    margin-top: 1;
+    margin-bottom: 0rem;
 }
 
 .chatEmptyStateSubtitle {
     font-weight: 600;
     margin-bottom: 0.625rem;
+    margin-top: 0.125rem;
+    padding-left: 1rem;
+    padding-right: 1rem;
+    text-align: center;
 }
 
 .chatMessageStream {
@@ -108,6 +112,10 @@
     margin-bottom: 1.25rem;
 }
 
+.appLogo {
+    width: 300px;
+    height: 60px;
+}
 @media (min-width: 992px) {
     .container {
         margin-top: 1.25rem;
@@ -118,7 +126,7 @@
     }
 
     .chatEmptyStateTitle {
-        font-size: 4rem;
+        font-size: 3rem;
     }
 
     .chatInput {
@@ -143,4 +151,8 @@
         max-width: 80%;
         min-width: 31.25rem;
     }
+    .appLogo {
+        width: 477px;
+        height: 91px;
+    }
 }
#### app/frontend/src/pages/chat/Chat.tsx
diff --git a/app/frontend/src/pages/chat/Chat.tsx b/app/frontend/src/pages/chat/Chat.tsx
index e3c0cfd..ed46aa3 100644
--- a/app/frontend/src/pages/chat/Chat.tsx
+++ b/app/frontend/src/pages/chat/Chat.tsx
@@ -4,7 +4,7 @@ import { Helmet } from "react-helmet-async";
 import { Panel, DefaultButton } from "@fluentui/react";
 import readNDJSONStream from "ndjson-readablestream";
 
-import appLogo from "../../assets/applogo.svg";
+import appLogo from "../../assets/applogo.png";
 import styles from "./Chat.module.css";
 
 import {
@@ -52,7 +52,7 @@ const Chat = () => {
     const [useSemanticCaptions, setUseSemanticCaptions] = useState<boolean>(false);
     const [includeCategory, setIncludeCategory] = useState<string>("");
     const [excludeCategory, setExcludeCategory] = useState<string>("");
-    const [useSuggestFollowupQuestions, setUseSuggestFollowupQuestions] = useState<boolean>(false);
+    const [useSuggestFollowupQuestions, setUseSuggestFollowupQuestions] = useState<boolean>(true);
     const [vectorFieldList, setVectorFieldList] = useState<VectorFieldOptions[]>([VectorFieldOptions.Embedding]);
     const [useOidSecurityFilter, setUseOidSecurityFilter] = useState<boolean>(false);
     const [useGroupsSecurityFilter, setUseGroupsSecurityFilter] = useState<boolean>(false);
@@ -363,14 +363,14 @@ const Chat = () => {
                 <div className={styles.commandsContainer}>
                     <ClearChatButton className={styles.commandButton} onClick={clearChat} disabled={!lastQuestionRef.current || isLoading} />
                     {showUserUpload && <UploadFile className={styles.commandButton} disabled={!loggedIn} />}
-                    <SettingsButton className={styles.commandButton} onClick={() => setIsConfigPanelOpen(!isConfigPanelOpen)} />
+                    {/* <SettingsButton className={styles.commandButton} onClick={() => setIsConfigPanelOpen(!isConfigPanelOpen)} /> */}
                 </div>
             </div>
             <div className={styles.chatRoot} style={{ marginLeft: isHistoryPanelOpen ? "300px" : "0" }}>
                 <div className={styles.chatContainer}>
                     {!lastQuestionRef.current ? (
                         <div className={styles.chatEmptyState}>
-                            <img src={appLogo} alt="App logo" width="120" height="120" />
+                            <img className={styles.appLogo} src="https://stjeegpqns5eeds.blob.core.windows.net/assets/eg-main-logo.webp" alt="App logo" />
 
                             <h1 className={styles.chatEmptyStateTitle}>{t("chatEmptyStateTitle")}</h1>
                             <h2 className={styles.chatEmptyStateSubtitle}>{t("chatEmptyStateSubtitle")}</h2>
@@ -481,7 +481,7 @@ const Chat = () => {
                         }}
                     />
                 )}
-
+                {/* 
                 <Panel
                     headerText={t("labels.headerText")}
                     isOpen={isConfigPanelOpen}
@@ -520,7 +520,7 @@ const Chat = () => {
                         onChange={handleSettingsChange}
                     />
                     {useLogin && <TokenClaimsDisplay />}
-                </Panel>
+                </Panel> */}
             </div>
         </div>
     );
#### app/frontend/src/pages/layout/Layout.module.css
diff --git a/app/frontend/src/pages/layout/Layout.module.css b/app/frontend/src/pages/layout/Layout.module.css
index 4854140..bd9ec18 100644
--- a/app/frontend/src/pages/layout/Layout.module.css
+++ b/app/frontend/src/pages/layout/Layout.module.css
@@ -33,6 +33,7 @@
 .headerTitle {
     margin-left: 0.5rem;
     font-weight: 600;
+    text-align: center;
 }
 
 .headerNavList {
#### app/frontend/src/pages/layout/Layout.tsx
diff --git a/app/frontend/src/pages/layout/Layout.tsx b/app/frontend/src/pages/layout/Layout.tsx
index 2086129..72ade3c 100644
--- a/app/frontend/src/pages/layout/Layout.tsx
+++ b/app/frontend/src/pages/layout/Layout.tsx
@@ -41,7 +41,7 @@ const Layout = () => {
                     <Link to="/" className={styles.headerTitleContainer}>
                         <h3 className={styles.headerTitle}>{t("headerTitle")}</h3>
                     </Link>
-                    <nav>
+                    {/* <nav>
                         <ul className={`${styles.headerNavList} ${menuOpen ? styles.show : ""}`}>
                             <li>
                                 <NavLink
@@ -62,7 +62,7 @@ const Layout = () => {
                                 </NavLink>
                             </li>
                         </ul>
-                    </nav>
+                    </nav> */}
                     <div className={styles.loginMenuContainer}>
                         {useLogin && <LoginButton />}
                         <IconButton
#### infra/core/storage/storage-account.bicep
diff --git a/infra/core/storage/storage-account.bicep b/infra/core/storage/storage-account.bicep
index 5dd98f1..aabf4aa 100644
--- a/infra/core/storage/storage-account.bicep
+++ b/infra/core/storage/storage-account.bicep
@@ -16,7 +16,7 @@ param defaultToOAuthAuthentication bool = false
 param deleteRetentionPolicy object = {}
 @allowed([ 'AzureDnsZone', 'Standard' ])
 param dnsEndpointType string = 'Standard'
-param isHnsEnabled bool = false
+param isHnsEnabled bool = true
 param kind string = 'StorageV2'
 param minimumTlsVersion string = 'TLS1_2'
 param supportsHttpsTrafficOnly bool = true
#### infra/main.bicep
diff --git a/infra/main.bicep b/infra/main.bicep
index 88d9a0e..a9cb352 100644
--- a/infra/main.bicep
+++ b/infra/main.bicep
@@ -35,6 +35,7 @@ param storageAccountName string = '' // Set in main.parameters.json
 param storageResourceGroupName string = '' // Set in main.parameters.json
 param storageResourceGroupLocation string = location
 param storageContainerName string = 'content'
+param assetStorageContainerName string = 'assets'
 param storageSkuName string // Set in main.parameters.json
 
 param userStorageAccountName string = ''
@@ -251,7 +252,7 @@ var resourceToken = toLower(uniqueString(subscription().id, environmentName, loc
 var tags = { 'azd-env-name': environmentName }
 
 var tenantIdForAuth = !empty(authTenantId) ? authTenantId : tenantId
-var authenticationIssuerUri = '${environment().authentication.loginEndpoint}${tenantIdForAuth}/v2.0'
+var authenticationIssuerUri = 'https://${tenantIdForAuth}.ciamlogin.com/${tenantIdForAuth}/v2.0'
 
 @description('Whether the deployment is running on GitHub Actions')
 param runningOnGh string = ''
@@ -755,8 +756,9 @@ module storage 'core/storage/storage-account.bicep' = {
     tags: tags
     publicNetworkAccess: publicNetworkAccess
     bypass: bypass
-    allowBlobPublicAccess: false
+    allowBlobPublicAccess: true
     allowSharedKeyAccess: false
+    isHnsEnabled: true
     sku: {
       name: storageSkuName
     }
@@ -773,6 +775,10 @@ module storage 'core/storage/storage-account.bicep' = {
         name: tokenStorageContainerName
         publicAccess: 'None'
       }
+      {
+        name: assetStorageContainerName
+        publicAccess: 'Blob'
+      }
     ]
   }
 }
@@ -790,7 +796,7 @@ module userStorage 'core/storage/storage-account.bicep' = if (useUserUpload) {
     bypass: bypass
     allowBlobPublicAccess: false
     allowSharedKeyAccess: false
-    isHnsEnabled: true
+    isHnsEnabled: false
     sku: {
       name: storageSkuName
     }
#### scripts/sampleacls.json
diff --git a/scripts/sampleacls.json b/scripts/sampleacls.json
index dd2d488..44a233f 100644
--- a/scripts/sampleacls.json
+++ b/scripts/sampleacls.json
@@ -1,38 +1,1369 @@
 {
     "files": {
-        "Benefit_Options.pdf": {
-            "directory": "benefitinfo"
+        "1-0 Quality Control Plan.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control"
         },
-        "employee_handbook.pdf": {
-            "directory": "employeeinfo"
+        "HUD 4000 1 QC Plan Review.xlsx.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control"
         },
-        "Northwind_Health_Plus_Benefits_Details.pdf": {
-            "directory": "benefitinfo"
+        "HUD QC Plan Review 8-23.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control"
         },
-        "Northwind_Standard_Benefits_Details.pdf": {
-            "directory": "benefitinfo"
+        "HUD QC Plan Revisions Locations - 3-14-22.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control"
         },
-        "PerksPlus.pdf": {
-            "directory": "benefitinfo"
+        "CFPB Examination Elements Matrix.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
         },
-        "role_library.pdf": {
-            "directory": "employeeinfo"
+        "FORM 1-1 QC Quality Control Review Spot Check Form - Loan Level QC Report.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-10 QC Occupancy Re-Verification.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-11 QC Reverification of Employment or Deposit Letter.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-1A QC DEL Loan Level Audit Report.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-2 QC Quality Control File Order Checklist.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-20 QC COMP OP HUD Site Review Checklist Form.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 1-3 QC ORIG PROC UW CLOS Fraud - Red Flag Checklist.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 1-30 QC Appraisal Review Log.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-31 QC UW PROC OP Checklist-Appraisal Review Form.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 1-32 QC Credit Report Log.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-34 QC Field Appraisal Review Request.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-4 QC Closed-Cancelled Audit Prep Financial-Compliance Checklist.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-40 QC Agency Pipeline Random Selection Tool.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-40 QC FHA Pipeline Random Selection Tool.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-41 QC FHA-Conv Pipeline Random Selection Tool.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-64 QC COMP CFPB Examination Elements Matrix.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-65 ORIG PROC UW CLOS QC Fraud - Red Flag Checklist.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-70 AML Red Flags Check -Transactional and High Risk Business.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 1-70 QC PROC UW CLOS AML Red Flags Checklist.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 1-70-1 QC AML-BSA Self Audit Checklist.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-70-7 AML Risk Assessment .pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-80 QC COMP Mortgage Risk Assessment (1).pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 3-1 ORIG PROC UW COMP Complete Application Checklist (Notice of Incomplete Application).pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 3-15 ORIG PROC UW CLOS COMP QC Notice of Changed Circumstances.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 3-8 ORIG PROC UW CLOS QC Notice of Changed Circumstances.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 4-02 PROC QC Appraisal Request.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 4-1 PROC UW QC Processing Underwriting Quality Control Production Checklist 3-2021.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-1 PROC UW QC Processing Underwriting Quality Control Production Checklist.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 4-1A QC PROC UW Master Production and Audit Quality Control Checklist.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 4-2 PROC QC Appraisal Request Form.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-31 PROC CLOS UW QC TRID Loan Estimate and Closing Disclosure Review.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 4-32 PROC QC Basic Loan Submission Process Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-33 PROC UW QC Processing Underwriting Quality Control Production Checklist.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 6-1 CLOS QC Pre-Funding Review and Document Preparation Checklist.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 6-10 CLOS QC SERV Post-Closing Document Review Checklist.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 6-11 CLOS QC SERV SEC Warehouse Insure-Guaranty and Closed Loan Delivery Checklist.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "FORM 6-2 CLOS QC Pre-Closing Document Prep Funding Review.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "Quality Control Plan Revew Checklist.pdf": {
+            "directory": "banker/1-0 Lender-Banker Quality Control/Forms"
+        },
+        "1-A Broker MiniC QC Plan.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan"
+        },
+        "CHART 4-51 PROC Document Naming Convention (1).pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "Complete Application Checklist (Notice of Incomplete Application).pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "Disclosures exhibits to Send and Retain - Broker and Lender.pdf": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "File Stack Order - Conventional.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 1-05 QC Occupancy Re-Verification.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-4 QC PROC Closed File Pre-Audit Compliance Checklist.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-5 Non-Del Quality Control Summary Report.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-5 Quality Control Report.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-65 QC ORIG PROC UW CLOS Fraud Red Flags Checklist.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 4-33 PROC UW QCProcessing Underwriting Quality Control Production Checklist.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM PROC 4-32 Basic Loan Submission Process Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM PROC UW QC 4-33 Processing Underwriting Quality Control Production Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Master Production and Audit Quality Control Checklist.pdf": {
+            "directory": "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "Pre-Underwriting Production Checklist - QC Master.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "2-0 Compliance Policies and Procedures.pdf": {
+            "directory": "banker/2-0 Compliance"
+        },
+        "Approved Appraiser Roster.pdf": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "Compliance Audit Checklist.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "Compliance Manager Duties and Schedule.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FACTA Disclosure Sample.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FairLendingPoster.pdf": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 1-65 QC COMP CFPB Examination Elements Matrix.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 2-35-26 COMP ORIG Reverse Mortgage Disclosure Sample.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 2-35-3 COMP 2NDRY High cost-fee Worksheet v2.pdf": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 2-71-1 ORIG COMP Anti-Steering Borrowers Best Interest Disclosure Safe Harbor.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 2-71-2 Current Compensation Plans.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 2-71-2 LO Comp Plan - Commissions - Individual.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 2-73-2 COMP ORIG PROC Borrower AIR Appraisal Notice.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 2-81 COMP OPS ORIG Complaint Report and Log.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 2-81 Complaint report.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 3-10 Loan Officer Compensation Plan Template Sample - REVIEW WITH COUNSEL.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-21 ORIG COMPL Advertising and Website Review Checklist.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 4-31 COMP ORIG PROC Borrower Appraisal Notice.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "FORM 7-26-1 OPS COMP New Hire Checklist.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "High cost-fee Worksheet v2.pdf": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "Non Traditional Loan Comparison Chart For Anti-Predatory Lending.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "Section 32 High Cost Worksheet.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "Tangible Net Benefit Certification.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "TRAIN 2-40 Fair Lending Laws.pdf": {
+            "directory": "banker/2-0 Compliance/Forms"
+        },
+        "2-01 Compliance Manager - Duties and Responsibilities.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-02 Federal Regulatory Compliance Program Overview.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-05 State Regulatory Compliance - Regulatory Highlight Checklist.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-10 RESPA Overview.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-11 RESPA - Prohibited - Kickbacks and Referral Fees.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-14 TRID Policies and Procedures.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-15 Reviewing Closing Disclosure CD or HUD-1 against LE-GFE Estimates.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-31 - TIL APR (Annual Percentage Rate) Calculations and Tolerance.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-32 TIL Additional Disclosures.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-33 Notice of Right to Cancel (Right to Rescind).pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-34 Advertising.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-35 Unfair Deceptive Abusive Acts and Practices - High Cost Loans - Predatory Lending.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-35-61 HPML Appraisal Policy.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-36 Mortgage Disclosure Improvement Act.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-37 Ability to Repay.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-40 Equal Credit Opportunity Act.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-42 HMDA Home Mortgage Disclosure Act.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-43 Fair Housing Act.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-44 Fair Credit Reporting Act.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-44-2 Credit Report Ordering Policies and Procedures.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-45 FACTA Overview.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-46 Homeowners Protection Act (PMI Cancellation).pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-47 Gramm-Leach-Bliley Privacy Act.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-47-2 PATRIOT Act and OFAC Policies and Procedures.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-48 E-SIGN Mortgage Procedures and Policies.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-70 SAFE Act.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-70-15 NMLS Call Reporting Process.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-71 Compensation and Anti-Steering.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-72 Pre- and Post-Employment Screening Procedure.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-72-4 Employee Training Policies and Procedures.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-73 Appraiser Independence Process.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-80 Complaint Resolution.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-81 Complaint Form Resolution and Report.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-97 Disaster Recovery and Business Continuity.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-A Policy in Practice QuickNotes.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "2-NY New York State Compliance Program.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "3-83 Ethics Policies and Procedures.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "3-84 Whistleblower Policy.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "7-10 Social Media Policy.pdf": {
+            "directory": "banker/7-0 Operations"
+        },
+        "PIP 1-70 Bank Secrecy Act_Anti-Money Laundering Procedures (1).pdf": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "PIP 1-85 Broker_Non-Delegated Correspondent QC Process.pdf": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "PIP 2-0 Regulatory Compliance Matrix (2).pdf": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "PIP 2-70 SAFE Act.pdf": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "PIP 2-73 AIR Appraiser Independence Rules (1).pdf": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "PIP 2-90 IT Security Policies and Procedures.pdf": {
+            "directory": "banker/2-0 Compliance Indexed"
+        },
+        "PIP 2-93 RED Flag ID Theft Policies and Procedures.pdf": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-90 IT Safeguarding and ID Theft.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft"
+        },
+        "2-90 FACTA-IDTheft-InfoSecurity.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "FORM - 2-92-1 Sample Data Breach Notification Letter - Freddie Mac.pdf": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM - 2-92-1 Sample Date Breach Notification - Loan Depot.pdf": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-90-25 IT Security Inventory.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "FORM 2-91-1 IT Vendor Review Checklist.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "FORM 2-92 Data Breach Analysis and Report.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "FORM 2-92-3 IT Information Security Vendor Program Verification.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "FORM 2-93-4 Red Flag Issue Report Form.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "FORM 2-94-1 Remote Work Setup Checklist.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "FORM 2-95 IT Protect your Identity Day.pdf": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-97-1 Disaster Preparation Checklist_Pre-Drill Assessment (2).pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "FORM 2-97-2 Fire Drill_Disaster Checklist and Report (1).pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "Front Door Unattended Sign.pdf": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "Poster - Clean Desk.pdf": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "Red Flag Matrix.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "Red Flag Plan Checklist.pdf": {
+            "directory": "banker/2-90 Information Security amd ID Theft/Forms"
+        },
+        "Side Door Sign.pdf": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "3-0 Origination Module.pdf": {
+            "directory": "banker/3-0 Origination"
+        },
+        "Advertising Checklist.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Best Interests Worksheet.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Borrower Appraisal Notice.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Borrowers Best Interest Disclosure (anti-steering).pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Call In Questionnaire.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Commissions Report.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-03 ORIG PROC Complete Application Checklist (Notice of Incomplete Application).pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-04 Homebuyers Finance Guide and Pre-Application Kit.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-09 ORIG Call In Questionnaire.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-13 ORIG COMP Pricing Exception Request.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-14 File Divider Loan Setup Checklists.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-25 Interest Rate Lock In Notification.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-25-1 ORIG COMP Pre-Qualification Letter.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-25-2 ORIG Pre-Qualification and Qualification Worksheet.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-30 Commissions Report.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-39 Loan Originator Employment Agreement - SAMPLE REVIEW WITH COUNSEL.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-41 ORIG COMP Call In Questionnaire.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-50 ORIG PROC Status Report.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-80 ORIG PROC CLOS Borrower Closing Preparation Worksheet.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-81 Loan Officer Intro Package.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM 3-82 Loan Officer Tracking Sheet.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "FORM ORIG 3-13 Pricing Exception Request.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Gift Letter.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Homebuyers Finance Guide and Pre-Application Kit.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Interest Rate Lock In Notification.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Loan Officer Intro Package.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Loan Originator Compensation Agreement.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Mortgage Loan Lock-in Agreement.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Mortgage Loan Lock-in Financing Agreement.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "Originator File Set Up Quality Control Review Checklist.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "SuperQual 12.pdf": {
+            "directory": "banker/3-0 Origination/Forms"
+        },
+        "4-0 Processing Module.pdf": {
+            "directory": "banker/4-0 Processing"
+        },
+        "1038-Net Rental Calculation.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "1084.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "Additional Information Request.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "Appraisal Request Form Sample.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Appraisal Request.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Approval Letter.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "Approved Appraiser Application.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Approved Appraiser Roster and Order Rotation.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Approved Appraiser Roster Sample.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Assignment Letter.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Basic Loan Submission Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Borrower's Certification & Authorization.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Closed Loan Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Closing Preparation Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Closing Requirement Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Comparative Income.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "Complete Application Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Condo - Homeowner's Insurance Request.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Condo PUD Letter.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Conventional Stacking Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Credit Report Fax Order-Correction.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "File Submission Process Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-01 PROC Loan File Set Up Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-02 PROC-QC Appraisal Request.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-03 PROC ORIG Condo PUD Letter.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-07 PROC File Stack Order - Conv-FHA-VA.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-08 PROC Additional Information Request.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-1 QC PROC UW Pre-Underwriting Production Checklist - Decision Tree.xls.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 4-11 Welcome Disclosure Package Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-11-1 Sample Welcome Package - Processing Merge Documents.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-13 Loan Log.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-1A QC PROC UW Master Production and Audit Quality Control Checklist.xls.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 4-2 Appraisal Request.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-26 PROC CLOS Condo PUD Homeowner Insurance Request.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-30 COMP ORIG PROC Borrower Appraisal Notice.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-31 PROC UW CLOS QC TRID Loan Estimate and Closing Disclosure Review.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 4-31 TRID Loan Estimate and Closing Disclosure Review PROC UW CLOS QC.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-35 Condo - Homeowner's Insurance Request.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-50 PROC ORIG Loan Level Status Log.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 4-64-03 PROC UW Income Calculation Worksheet.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM 4-64-41 PROC Income Analysis - Simple.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM 5-10 UW Underwriter Worksheet.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "FORM DISC 4-31 Borrower Appraisal Notice.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM DISC 4-50 Borrower's Certification & Authorization.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM PROC 4-01 Loan File Set Up Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM PROC 4-03 Condo PUD Letter.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM PROC 4-07 File Stack Order - Conv-FHA-VA.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM PROC 4-08 Additional Information Request.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM PROC 4-64-41 Income Analysis - Simple.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM PROC UW 4-64-03 Income Calculation Worksheet.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "FORM PROC-QC 4-02 Appraisal Request.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Income Analysis - Simple.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "IncomeCalculationWorksheet.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Loan File Set Up Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Loan Log.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Loan Plan Specification Review.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Loan Specifications - FHA.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "MDIA TIL Broker Addendum.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "MGIC Self-Employed and Rental Income Analysis (Fillable) 12-10-2014.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "Notice of Changed Circumstances - GFE-2010.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Radian Self-Employment Cash Flow and Rental Income Analysis Calculator12-14.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "Random Appraisal Order Form.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "SE AGI Method Analysis.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "SE Schedule Analysis.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Simple Income Analysis.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "T-I-L Explanation.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Underwriting Analysis Report-Approval Notification.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "Verbal Employment Verification.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "Verbal Verification of Employment.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "verbal voe.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Welcome Disclosure Package Checklist.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "Welcome Package - Processing Merge Documents.pdf": {
+            "directory": "banker/4-0 Processing/Forms"
+        },
+        "5-0 Underwriting Module.pdf": {
+            "directory": "banker/5-0 Underwriting"
+        },
+        "SampleATRPolicy.pdf": {
+            "directory": "banker/5-0 Underwriting"
+        },
+        "Appraiser Approval Application.pdf": {
+            "directory": "banker/5-0 Underwriting/Forms"
+        },
+        "6-0 Closing Module.pdf": {
+            "directory": "banker/6-0 Closing"
+        },
+        "FORM CLOS 1 Pre-Funding Review and Document Preparation Checklist.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM CLOS 10 Post-Closing Document Review Checklist.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM CLOS 11 Warehouse Insure-Guaranty and Closed Loan Delivery Checklist.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM CLOS 12 FHA-HUD Endorsement Binder Stack Order Checklist.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM CLOS 21 Approved Attorney Application.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM CLOS 31 Settlement Exception Report.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM CLOS 4 Fee Sheet.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM CLOS 41 Condominium Document Management System Checklist.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM CLOS 5 Closing Notification Tickler.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM CLOS 8 Warehouse Funding Calculations.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM ORIG 8 Notice of Changed Circumstances.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "FORM PROC 26 Condo PUD Homeowner Insurance Request.pdf": {
+            "directory": "banker/6-0 Closing/Forms"
+        },
+        "7-0 Operations Module.pdf": {
+            "directory": "banker/7-0 Operations"
+        },
+        "7-20 Disaster Recovery \u2013 Business Continuity Plan.pdf": {
+            "directory": "banker/7-0 Operations"
+        },
+        "7-A Employee Handbook.pdf": {
+            "directory": "banker/7-0 Operations"
+        },
+        "Approved Vendor Application.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Employee Roster.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Incoming Document Log.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Leave Tracking.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Loan Officer Tracking Sheet.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "New Hire Reference Check Form.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Office Supply List.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Outgoing Document Log.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Performance Appraisal - Training Cover.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Performance Appraisal.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Time Sheet for Non-Exempt Employees.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Time Sheet.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Title 1 Dealer Contractor Approval Checklist.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Title I Dealer Contractor Approval.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "Vendor Approval - Renewal Application.pdf": {
+            "directory": "banker/7-0 Operations/Forms"
+        },
+        "1-A Broker MiniC QC Plan.docx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan"
+        },
+        "CHART 4-51 PROC Document Naming Convention (1).xlsx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "Complete Application Checklist (Notice of Incomplete Application).docx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "File Stack Order - Conventional.xls": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-05 QC Occupancy Re-Verification.doc": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-4 QC PROC Closed File Pre-Audit Compliance Checklist.docx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-5 Non-Del Quality Control Summary Report.xlsx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-5 Quality Control Report.docx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-65 ORIG PROC UW CLOS QC Fraud - Red Flag Checklist.docx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-65 QC ORIG PROC UW CLOS Fraud Red Flags Checklist.doc": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-70 QC PROC UW CLOS AML Red Flags Checklist.docx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-70-1 QC AML-BSA Self Audit Checklist.xlsx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-70-6 Beneficial Interest Appendix A .docx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-70-7 AML Risk Assessment .xlsx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 1-80 QC COMP Mortgage Risk Assessment (1).xlsx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 3-1 ORIG PROC UW COMP Complete Application Checklist (Notice of Incomplete Application).docx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 4-1 PROC UW QC Processing Underwriting Quality Control Production Checklist 3-2021.xlsx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM 4-33 PROC UW QCProcessing Underwriting Quality Control Production Checklist.xlsx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM PROC 4-32 Basic Loan Submission Process Checklist.xlsx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "FORM PROC UW QC 4-33 Processing Underwriting Quality Control Production Checklist.xlsx": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "Master Production and Audit Quality Control Checklist.xls": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "Pre-Underwriting Production Checklist - QC Master.xls": {
+            "directory": "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms"
+        },
+        "2-0 Compliance Policies and Procedures.docx": {
+            "directory": "broker compliance/2-0 Compliance"
+        },
+        "Compliance Audit Checklist.xls": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "Compliance Manager Duties and Schedule.xlsx": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FACTA Disclosure Sample.doc": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 1-20 QC COMP OP HUD Site Review Checklist Form.doc": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 1-65 QC COMP CFPB Examination Elements Matrix.doc": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 2-35-26 COMP ORIG Reverse Mortgage Disclosure Sample.docx": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 2-71-1 ORIG COMP Anti-Steering Borrowers Best Interest Disclosure Safe Harbor.xls": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 2-71-2 Current Compensation Plans.xlsx": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 2-71-2 LO Comp Plan - Commissions - Individual.docx": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 2-73-2 COMP ORIG PROC Borrower AIR Appraisal Notice.doc": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 2-81 COMP OPS ORIG Complaint Report and Log.xls": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 2-81 Complaint report.doc": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 3-10 Loan Officer Compensation Plan Template Sample - REVIEW WITH COUNSEL.docx": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 3-10 ORIG COMP Loan Officer Compensation Plan Draft 9-2013.gdoc": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 3-15 ORIG PROC UW CLOS COMP QC Notice of Changed Circumstances.doc": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 3-21 ORIG COMPL Advertising and Website Review Checklist.xlsx": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 4-31 COMP ORIG PROC Borrower Appraisal Notice.docx": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "FORM 7-26-1 OPS COMP New Hire Checklist.docx": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "Non Traditional Loan Comparison Chart For Anti-Predatory Lending.doc": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "Section 32 High Cost Worksheet.xls": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "Tangible Net Benefit Certification.doc": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "TRAIN 2-40 Fair Lending Laws.ppt": {
+            "directory": "broker compliance/2-0 Compliance/Compliance Forms"
+        },
+        "11-18-22 AIR Update.htm": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-01 Compliance Manager - Duties and Responsibilities.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-02 Federal Regulatory Compliance Program Overview.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-05 State Regulatory Compliance - Regulatory Highlight Checklist.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-10 RESPA Overview.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-11 RESPA - Prohibited - Kickbacks and Referral Fees.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-14 TRID Policies and Procedures.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-15 Reviewing Closing Disclosure CD or HUD-1 against LE-GFE Estimates.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-31 - TIL APR (Annual Percentage Rate) Calculations and Tolerance.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-32 TIL Additional Disclosures.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-33 Notice of Right to Cancel (Right to Rescind).docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-34 Advertising.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-35 Unfair Deceptive Abusive Acts and Practices - High Cost Loans - Predatory Lending.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-35-61 HPML Appraisal Policy.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-36 Mortgage Disclosure Improvement Act.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-37 Ability to Repay.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-40 Equal Credit Opportunity Act.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-42 HMDA Home Mortgage Disclosure Act.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-43 Fair Housing Act.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-44 Fair Credit Reporting Act.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-44-2 Credit Report Ordering Policies and Procedures.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-45 FACTA Overview.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-46 Homeowners Protection Act (PMI Cancellation).docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-47 Gramm-Leach-Bliley Privacy Act.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-47-2 PATRIOT Act and OFAC Policies and Procedures.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-48 E-SIGN Mortgage Procedures and Policies.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-70 SAFE Act.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-70-15 NMLS Call Reporting Process.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-71 Compensation and Anti-Steering.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-72 Pre- and Post-Employment Screening Procedure.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-72-4 Employee Training Policies and Procedures.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-73 Appraiser Independence Process.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-80 Complaint Resolution.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-81 Complaint Form Resolution and Report.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-97 Disaster Recovery and Business Continuity.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-A Policy in Practice QuickNotes.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-NY New York State Compliance Program.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "3-83 Ethics Policies and Procedures.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "3-84 Whistleblower Policy.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "7-10 Social Media Policy.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "PIP 2-90 IT Security Policies and Procedures.docx": {
+            "directory": "broker compliance/2-0 Compliance Indexed"
+        },
+        "2-90 IT Safeguarding and ID Theft.docx": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft"
+        },
+        "Annual ITCyber Security Audit Customers.htm.htm": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft"
+        },
+        "Remote Work Policy Update.htm.htm": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft"
+        },
+        "2-90 FACTA-IDTheft-InfoSecurity.PPT": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-90-25 IT Security Inventory.xlsx": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-91-1 IT Vendor Review Checklist.docx": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-92 Data Breach Analysis and Report.xlsx": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-92-3 IT Information Security Vendor Program Verification.xls": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-93-4 Red Flag Issue Report Form.doc": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-94-1 Remote Work Setup Checklist.xlsx": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-97-1 Disaster Preparation Checklist_Pre-Drill Assessment (2).xlsx": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "FORM 2-97-2 Fire Drill_Disaster Checklist and Report (1).xlsx": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "Red Flag Matrix.xls": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
+        },
+        "Red Flag Plan Checklist.xls": {
+            "directory": "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits"
         }
     },
     "directories": {
-        "employeeinfo": {
-            "groups": ["GPTKB_HRTest"]
+        "banker": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
         },
-        "benefitinfo": {
-            "groups": ["GPTKB_EmployeeTest", "GPTKB_HRTest"]
+        "broker compliance": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-broker-compliance"
+            ]
         },
         "/": {
-            "groups": ["GPTKB_AdminTest"]
+            "groups": [
+                "eg-admin",
+                "mm-admin"
+            ]
+        },
+        "banker/1-0 Lender-Banker Quality Control": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/1-0 Lender-Banker Quality Control/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/1-A Broker Mini-C Non-Delegated QC Plan": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/1-A Broker Mini-C Non-Delegated QC Plan/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/2-0 Compliance": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/2-0 Compliance/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/2-0 Compliance Indexed": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/2-90 Information Security amd ID Theft": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/2-90 Information Security amd ID Theft/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/3-0 Origination": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/3-0 Origination/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/4-0 Processing": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/4-0 Processing/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/5-0 Underwriting": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/5-0 Underwriting/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/6-0 Closing": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/6-0 Closing/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/7-0 Operations": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "banker/7-0 Operations/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-banker"
+            ]
+        },
+        "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-broker-compliance"
+            ]
+        },
+        "broker compliance/1-A Broker Mini-C Non-Delegated QC Plan/Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-broker-compliance"
+            ]
+        },
+        "broker compliance/2-0 Compliance": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-broker-compliance"
+            ]
+        },
+        "broker compliance/2-0 Compliance/Compliance Forms": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-broker-compliance"
+            ]
+        },
+        "broker compliance/2-0 Compliance Indexed": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-broker-compliance"
+            ]
+        },
+        "broker compliance/2-90 Information Security and ID Theft": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-broker-compliance"
+            ]
+        },
+        "broker compliance/2-90 Information Security and ID Theft/Forms and Exhibits": {
+            "groups": [
+                "eg-admin",
+                "mm-admin",
+                "mm-broker-compliance"
+            ]
         }
     },
     "groups": [
-        "GPTKB_AdminTest",
-        "GPTKB_HRTest",
-        "GPTKB_EmployeeTest"
+        "eg-admin",
+        "mm-admin",
+        "mm-banker",
+        "mm-broker-compliance"
     ]
-}
+}
\ No newline at end of file


---
Generated on: 2025-02-24 13:41:14

### Changes made:

- .azure/pai-mm-prod/.env-temp
- app/backend/prepdocslib/searchmanager.py
- scripts/generate_git_commit_message.py

### Detailed changes:

#### .azure/pai-mm-prod/.env-temp
diff --git a/.azure/pai-mm-prod/.env-temp b/.azure/pai-mm-prod/.env-temp
index adad91f..2983b9f 100644
--- a/.azure/pai-mm-prod/.env-temp
+++ b/.azure/pai-mm-prod/.env-temp
@@ -1,5 +1,4 @@
 AZURE_AUTH_TENANT_ID=""
-AZURE_ADLS_GEN2_STORAGE_ACCOUNT=""
 AZURE_COSMOSDB_LOCATION="centralus"
 AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS="true"
 AZURE_ENFORCE_ACCESS_CONTROL="true"
#### app/backend/prepdocslib/searchmanager.py
diff --git a/app/backend/prepdocslib/searchmanager.py b/app/backend/prepdocslib/searchmanager.py
index f75af03..314e4fd 100644
--- a/app/backend/prepdocslib/searchmanager.py
+++ b/app/backend/prepdocslib/searchmanager.py
@@ -103,7 +103,11 @@ class SearchManager:
                         vector_search_dimensions=self.embedding_dimensions,
                         vector_search_profile_name="embedding_config",
                     ),
-                    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
+                    SimpleField(
+                        name="category", 
+                        type="Edm.String", 
+                        filterable=True, 
+                        facetable=True),
                     SimpleField(
                         name="sourcepage",
                         type="Edm.String",
@@ -122,22 +126,18 @@ class SearchManager:
                         filterable=True,
                         facetable=False,
                     ),
-                ]
-                if self.use_acls:
-                    fields.append(
-                        SimpleField(
-                            name="oids",
-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
-                            filterable=True,
-                        )
-                    )
-                    fields.append(
-                        SimpleField(
-                            name="groups",
-                            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
-                            filterable=True,
-                        )
+                    SimpleField(
+                        name="oids",
+                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+                        filterable=True,
+                    ),
+                    SimpleField(
+                        name="groups",
+                        type=SearchFieldDataType.Collection(SearchFieldDataType.String),
+                        filterable=True,
                     )
+                ]
+                    
                 if self.use_int_vectorization:
                     logger.info("Including parent_id field in new index %s", self.search_info.index_name)
                     fields.append(SearchableField(name="parent_id", type="Edm.String", filterable=True))
#### scripts/generate_git_commit_message.py
diff --git a/scripts/generate_git_commit_message.py b/scripts/generate_git_commit_message.py
index 171fb03..00790e8 100644
--- a/scripts/generate_git_commit_message.py
+++ b/scripts/generate_git_commit_message.py
@@ -27,11 +27,11 @@ def get_file_diff(file_path):
 
 def prepend_to_changelog(new_content):
     changelog_path = "CHANGELOG.md"
-    # if os.path.exists(changelog_path):
-    #     with open(changelog_path, "r") as f:
-    #         existing_content = f.read()
-    # else:
-    #     existing_content = ""
+    if os.path.exists(changelog_path):
+        with open(changelog_path, "r") as f:
+            existing_content = f.read()
+    else:
+        existing_content = ""
 
     with open(changelog_path, "a") as f:
         f.write(new_content + "\n\n")


