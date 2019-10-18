using System;
using System.Collections.Generic;
using System.Text;

namespace doc_loader_http_elastic
{
    class PlainDocument
    {
        private string page ;
        private DateTime uploadedAt;
        public string Page { get => page; set => page = value; }
        public DateTime UploadedAt { get => uploadedAt; set => uploadedAt = value; }
    }
}
