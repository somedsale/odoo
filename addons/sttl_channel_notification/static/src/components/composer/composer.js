/** @odoo-module **/

import { ThreadService } from "@mail/core/common/thread_service";
import { patch } from "@web/core/utils/patch";
import { prettifyMessageContent } from "@mail/utils/common/format";

const threadServicePatch = {
  async getMessagePostParams(params){
       const subtype = params['isNote'] ? "mail.mt_note" : "mail.mt_comment";
       const validMentions = this.store.user
           ? this.messageService.getMentionsFromText(params['body'], {
                 mentionedChannels:params['mentionedChannels'],
                 mentionedPartners:params['mentionedPartners'],
             })
           : undefined;
      const body_content = await prettifyMessageContent(params['body'], validMentions)      
      if (body_content.includes('model=discuss.channel')) {
        let splitText = body_content.split(' ')
        let channels = []
        for (let i = 0; i < splitText.length; i++) {
            if (splitText[i].includes('model=discuss.channel')) {
                let channelIdIndex = splitText[i].indexOf('id=');
                if (channelIdIndex !== -1) {
                    // Extract the id value by slicing the string starting after 'id=' and until the next '&' or end of string
                    let channelId = splitText[i].substring(channelIdIndex + 3).split('&')[0];                                         
                    channelId = channelId.replace('"', '')                    
                    channels.push(channelId);
                }
            }

        }    
        let parameters = {
            'channels': channels,
            'body': body_content,  
            'model': params['thread'].model,
            'record': params['thread'].id   
        }                        
          const channelData = await this.rpc("/mail/get_channels", parameters);
    }
      return super.getMessagePostParams(params);
  }
}

patch(ThreadService.prototype, threadServicePatch);
