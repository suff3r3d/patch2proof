FROM eclipse-temurin:21-jdk

WORKDIR /app
COPY . /app

# Case owners should pin dependencies and choose the reviewed test entrypoint.
ENTRYPOINT ["sh", "-c"]
