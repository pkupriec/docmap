
using System;
using System.Collections.Generic;
using static Google.Cloud.Language.V1.AnnotateTextRequest.Types;
using Google.Protobuf.Collections;
using Google.Cloud.Language.V1;

namespace elastic_doc_processor
{
    class GoogleNaturalLanguageAPI
    {
        private static AnalyzeEntitiesResponse AnalyzeEntitiesFromText(string text)
        {
            var GoogleLanguageServiceClientclient = LanguageServiceClient.Create();
            var response = GoogleLanguageServiceClientclient.AnalyzeEntities(new Document()
            {
                Content = text,
                Type = Document.Types.Type.PlainText
            });
            return response;
        }
    }
}
