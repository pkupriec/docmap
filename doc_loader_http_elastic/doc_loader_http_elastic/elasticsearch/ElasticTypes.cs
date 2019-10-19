using System;
using System.Collections.Generic;
using System.Text;

namespace doc_loader_http_elastic
{
    class PlainDocument
    {
        private string pageSource ;
        private DateTime uploadedAt;
        private string Id;
        public string PageSource { get => pageSource; set => pageSource = value; }
        public DateTime UploadedAt { get => uploadedAt; set => uploadedAt = value; }
        public string id { get => Id; set => Id = value; }
    }
}
