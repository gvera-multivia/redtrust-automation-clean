import * as constants from './constants.js';
// @ts-ignore
import * as console from './console.js';

let extensionVersion = constants.defaultVersion;

export function calculateSimilarity(str1, str2) {
    let similarity = calculatePercentajeSimilarity(str1, str2);
    if (similarity >= constants.SIMILARITY_THRESHOLD) {
        const regex = /[0-9]/gi;
        const updatedelement = str2.replace(regex, "");
        const updatedhost = str1.replace(regex, "");
        return updatedelement === updatedhost;
    }
    return false;
}

function calculatePercentajeSimilarity(str1, str2) {
    if (str1 == str2) {
        return 1.0;
    }
    let stepsToSame = levenshteinDistance(str1, str2);
    return (1.0 - (stepsToSame / Math.max(str1.length, str2.length)));
}

function levenshteinDistance(str1, str2) {
    const m = str1.length;
    const n = str2.length;

    // Create a 2D matrix to store the distances
    const dp = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0));

    // Initialize the first row and column of the matrix
    for (let i = 0; i <= m; i++) {
        dp[i][0] = i;
    }
    for (let j = 0; j <= n; j++) {
        dp[0][j] = j;
    }

    // Fill in the rest of the matrix
    for (let i = 1; i <= m; i++) {
        for (let j = 1; j <= n; j++) {
            // If the characters are equal, no edit needed
            if (str1[i - 1] === str2[j - 1]) {
                dp[i][j] = dp[i - 1][j - 1];
            }
            else {
                // Find the minimum edit distance
                dp[i][j] = Math.min(
                    dp[i - 1][j] + 1, // Deletion
                    dp[i][j - 1] + 1, // Insertion
                    dp[i - 1][j - 1] + 1 // Substitution
                );
            }
        }
    }

    // The final value in the matrix represents the Levenshtein distance
    return dp[m][n];
}

export function checkSimilarityBetweenHostnames(domain1, domain2) {
    const minParts = 2;
    let result = false
    const arr1 = domain1.split('.');
    const arr2 = domain2.split('.');
    arr1.reverse();
    arr2.reverse();
    let equal_length = (arr1.length == arr2.length);
    let partsToEvaluate = Math.min(arr1.length, arr2.length);
    if (partsToEvaluate >= minParts) {
        if (equal_length && partsToEvaluate > 2) {
            // Last part is discarded.
            partsToEvaluate--;
        }
        // Check if the first n elements are equal
        let i = 0;
        result = true
        while (i < partsToEvaluate && result) {
            result = (arr1[i] === arr2[i]);
            i++;
        }
    }
    return result;
}

export function isNullOrEmpty(str) {
    return  !str || String(str).trim().length === 0;
}


export function getBrowsingPositionKey(windowId, tabId)
{
    return `${windowId}-${tabId}`;
}

export function getTabItem(url, message, completed)
{   
    return {url : url, message : message, completed : completed };
}

export function getExtensionId() {
    // @ts-ignore
    return chrome.runtime ? chrome.runtime.id : browser.runtime.id;
}
export function isFirefox()
{
    return navigator.userAgent.toLowerCase().indexOf("firefox") > -1
}
export function isURL(url)
{
    try
    {
        let urlResult = new URL(url);
        return true;
    }
    catch(error)
    {
        return false;
    }
}
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
/////////////////////////       HANDLING VERSION    ///////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////////
export function isVersion1() {
    return extensionVersion == constants.defaultVersion;
}

export function isVersion2() {
    return extensionVersion == constants.catchUrlVersion;
}

// @ts-ignore
export function setCurrentVersion(version) {
    extensionVersion = constants.catchUrlVersion;
}

