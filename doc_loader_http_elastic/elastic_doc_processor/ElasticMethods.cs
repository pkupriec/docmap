using System;
using System.Collections.Generic;
using System.Text;
using Nest;

namespace elastic_doc_processor
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
    }
}
