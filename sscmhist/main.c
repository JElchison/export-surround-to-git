#include <stdio.h>
#include <stdlib.h>
#include "sscmapi.h"

int main(int argc, char *argv[])
{
    const char *pHost = NULL;
    unsigned int port = 4900;
    const char *pUsername = NULL;
    const char *pPassword = NULL;
    const char *pRepo = NULL;
    const char *pFile = NULL;
    unsigned int version = 0;
    struct SSCMContext context;
    struct FileHistoryItem **ppItems = NULL;
    int numOfHistoryItems = -1;
    int ret = 1;

    pHost = argv[1];
    port = atoi(argv[2]);
    pUsername = argv[3];
    pPassword = argv[4];
    context.pMainline = argv[5];
    context.pBranch = argv[6];
    pRepo = argv[7];
    pFile = argv[8];
    if (argc >= 10) {
        version = atoi(argv[9]);
    }

    context.cbSize = sizeof(struct SSCMContext);
    SSCMResult result = sscm_connect(pHost, port, pUsername, pPassword, &context);
    if (result != SSCM_API_OK) {
        char *pError = sscm_get_last_error(result);
        printf("sscm_connect failed: %s\n", pError);
        sscm_free_string(pError);
        goto END;
    }
    
    result = sscm_file_history(&context,
                               pRepo,
                               pFile,
                               0, // No workflow state changes
                               0, // No custom field changes
                               AllActions,
                               &ppItems,
                               &numOfHistoryItems);
    if (result != SSCM_API_OK) {
        char *pError = sscm_get_last_error(result);
        printf("sscm_file_history failed: %s\n", pError);
        sscm_free_string(pError);
        goto END;
    }
    
    if (version == 0) {
        printf("version\tdate\taction\tactionBranch\tactionVersion\tusername\n");
    }

    for (int i = 0; i < numOfHistoryItems; i++) {
        if (version == 0 || ppItems[i]->version == version) {
            printf("%u\t%u\t%d\t%s\t%u\t%s\n",
                   ppItems[i]->version,
                   (unsigned int) ppItems[i]->date,
                   ppItems[i]->action,
                   ppItems[i]->pActionBranch,
                   ppItems[i]->actionVersion,
                   ppItems[i]->pUsername);
        }
    }
    
    ret = 0;

END:
    if (ppItems != NULL) {
        sscm_free_history_itemlist(ppItems, numOfHistoryItems);
    }

    sscm_disconnect(&context);

    return ret;
}
