import React from "react";
import styles from "./Footer.module.css";

export const Footer = () => {
    const year = new Date().getFullYear();
    return (
        <footer className={styles.footer}>
            <a href="https://entelligage.com/" target="_blank">
                <img src="https://stjeegpqns5eeds.blob.core.windows.net/assets/EntelligageAI-Banner.png" alt="Logo" className={styles.logo} />
            </a>
            <div className={styles.links}>
                <a href="https://entelligage.com/privacy-policy" target="_blank" style={{ color: "white" }}>
                    Privacy Policy
                </a>
                <a href="https://entelligage.com/terms" target="_blank" style={{ color: "white" }}>
                    Terms
                </a>
                <a href="https://entelligage.com/disclaimer" target="_blank" style={{ color: "white" }}>
                    Disclaimer
                </a>
                <a href="https://entelligage.com/acceptable-use" target="_blank" style={{ color: "white" }}>
                    Acceptable Use
                </a>
            </div>
            <div className={styles.stackedLinks}>
                <a href="https://entelligage.com/" target="_blank" className={styles.rightLink} style={{ color: "white" }}>
                    &copy; {year} Entelligage Inc., All Rights Reserved.
                </a>
                <a href="https://mortgagemanuals.com/" target="_blank" className={styles.rightLink} style={{ color: "white" }}>
                    &copy; {year} Mortgage Manuals, All Rights Reserved.
                </a>
            </div>
        </footer>
    );
};
