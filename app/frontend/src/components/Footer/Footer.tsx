import React from "react";
import styles from "./Footer.module.css";

export const Footer = () => {
    const year = new Date().getFullYear();
    return (
        <footer className={styles.footer}>
            <div className={styles.stackedLinks}>
                <a href="https://entelligage.com/" target="_blank" className={styles.egLogo}>
                    <img src="https://stjeegpqns5eeds.blob.core.windows.net/assets/EntelligageAI-Banner.png" alt="Logo" className={styles.logo} />
                </a>
                <div className={styles.smallCopyRight}>
                    &copy; {year} Entelligage Inc. <br />
                    All Rights Reserved
                </div>
                <div className={styles.copyRight}>&copy; {year} Entelligage Inc. All Rights Reserved</div>
            </div>
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
            <a href="https://mortgagemanuals.com/" target="_blank">
                <div className={styles.smallRightLink}>
                    &copy; {year} Mortgage Manuals
                    <br />
                    All Rights Reserved.
                </div>
                <div className={styles.rightLink}>&copy; {year} Mortgage Manuals, All Rights Reserved.</div>
            </a>
        </footer>
    );
};
