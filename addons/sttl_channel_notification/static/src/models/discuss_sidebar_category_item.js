/** @odoo-module **/
import { ThreadService } from "@mail/core/common/thread_service";
import { patch } from "@web/core/utils/patch";

const threadServicePatch = {
    getCounter(thread) {
        if (thread.type === "mailbox") {
            return thread.message_unread_counter;
        }
        if (thread.isChatChannel) {
            return thread.message_unread_counter ;
        }
        return thread.message_unread_counter;    
    }
}


patch(ThreadService.prototype, threadServicePatch);
