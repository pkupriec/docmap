FROM mcr.microsoft.com/dotnet/core/runtime:3.0-buster-slim AS base
WORKDIR /app

FROM mcr.microsoft.com/dotnet/core/sdk:3.0-buster AS build
WORKDIR /src
COPY ["elastic_doc_processor/elastic_doc_processor.csproj", "elastic_doc_processor/"]
RUN dotnet restore "elastic_doc_processor/elastic_doc_processor.csproj"
COPY "elastic_doc_processor/" .
WORKDIR "/src/elastic_doc_processor"
RUN dotnet build "elastic_doc_processor.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "elastic_doc_processor.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "elastic_doc_processor.dll"]