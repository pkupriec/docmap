using System;
using System.Collections.Generic;
using System.Text;
using Nest;

namespace doc_loader_http_elastic
{
    class ElasticInteractionWrapper
    {
        ElasticClient Client;
        ConnectionSettings ElasticConnectionSettings;
        Uri ElasticUri;
        public void OpenElasticConnection() { 

             ElasticUri = new Uri("http://104.197.115.64:9200");
             ElasticConnectionSettings = new ConnectionSettings(ElasticUri)
                .BasicAuthentication("elastic", "elpass")
                .DisableAutomaticProxyDetection()
                .DisableDirectStreaming()
                .PrettyJson()
                .DefaultIndex("scp_source_pages")
                .RequestTimeout(TimeSpan.FromMinutes(2));
             Client = new ElasticClient(ElasticConnectionSettings);
        }
        public IndexResponse SaveDocument (PlainDocument document)
        {
             return Client.IndexDocument(document);
        }
        

    }
}
