import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import styles from "./HistoryItem.module.css";
import { DefaultButton } from "@fluentui/react";
import { Delete24Regular, Edit24Regular } from "@fluentui/react-icons";

export interface HistoryData {
    id: string;
    title: string;
    timestamp: number;
}

interface HistoryItemProps {
    item: HistoryData;
    onSelect: (id: string) => void;
    onDelete: (id: string) => void;
    onUpdateTitle: (id: string, title: string) => void;
}

export function HistoryItem({ item, onSelect, onDelete, onUpdateTitle }: HistoryItemProps) {
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [newTitle, setNewTitle] = useState(item.title);

    const handleDelete = useCallback(() => {
        setIsDeleteModalOpen(false);
        onDelete(item.id);
    }, [item.id, onDelete]);

    const handleUpdateTitle = useCallback(() => {
        setIsEditModalOpen(false);
        onUpdateTitle(item.id, newTitle);
    }, [item.id, newTitle, onUpdateTitle]);

    return (
        <div className={styles.historyItem}>
            <button onClick={() => onSelect(item.id)} className={styles.historyItemButton}>
                <div className={styles.historyItemTitle}>{item.title}</div>
            </button>
            <button onClick={() => setIsEditModalOpen(true)} className={styles.editButton} aria-label="edit this chat history">
                <Edit24Regular className={styles.editIcon} />
            </button>
            <button onClick={() => setIsDeleteModalOpen(true)} className={styles.deleteButton} aria-label="delete this chat history">
                <Delete24Regular className={styles.deleteIcon} />
            </button>
            <DeleteHistoryModal isOpen={isDeleteModalOpen} onClose={() => setIsDeleteModalOpen(false)} onConfirm={handleDelete} />
            <EditHistoryModal
                isOpen={isEditModalOpen}
                onClose={() => setIsEditModalOpen(false)}
                newTitle={newTitle}
                setNewTitle={setNewTitle}
                onConfirm={handleUpdateTitle}
            />
        </div>
    );
}

function DeleteHistoryModal({ isOpen, onClose, onConfirm }: { isOpen: boolean; onClose: () => void; onConfirm: () => void }) {
    if (!isOpen) return null;
    const { t } = useTranslation();
    return (
        <div className={styles.modalOverlay}>
            <div className={styles.modalContent}>
                <h2 className={styles.modalTitle}>{t("history.deleteModalTitle")}</h2>
                <p className={styles.modalDescription}>{t("history.deleteModalDescription")}</p>
                <div className={styles.modalActions}>
                    <DefaultButton onClick={onClose} className={styles.modalCancelButton}>
                        {t("history.cancelLabel")}
                    </DefaultButton>
                    <DefaultButton onClick={onConfirm} className={styles.modalConfirmButton}>
                        {t("history.deleteLabel")}
                    </DefaultButton>
                </div>
            </div>
        </div>
    );
}

function EditHistoryModal({
    isOpen,
    onClose,
    newTitle,
    setNewTitle,
    onConfirm
}: {
    isOpen: boolean;
    onClose: () => void;
    newTitle: string;
    setNewTitle: (title: string) => void;
    onConfirm: () => void;
}) {
    if (!isOpen) return null;
    const { t } = useTranslation();
    return (
        <div className={styles.modalOverlay}>
            <div className={styles.modalContent}>
                <h2 className={styles.modalTitle}>{t("history.editModalTitle")}</h2>
                <input
                    type="text"
                    value={newTitle}
                    onChange={e => setNewTitle(e.target.value)}
                    className={styles.modalInput}
                    placeholder={t("history.editModalPlaceholder")}
                />
                <div className={styles.modalActions}>
                    <DefaultButton onClick={onClose} className={styles.modalCancelButton}>
                        {t("history.cancelLabel")}
                    </DefaultButton>
                    <DefaultButton onClick={onConfirm} className={styles.modalSubmitButton}>
                        {t("history.submitLabel")}
                    </DefaultButton>
                </div>
            </div>
        </div>
    );
}
