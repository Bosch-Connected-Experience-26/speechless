# **Your Team at a Glance**

## **Team Name / Tagline**

*[Brief catchy tagline or team name]*

> 💡 **Tip:** Create a sheet of paper with your team name on the desk so mentors and organizers can find you easily! 

*[Feel free to include a picture representing your team here]*

## **Team Members**

| Name | GitHub Handle | Role(s) |
| :--- | :--- | :--- |
| Firstname Lastname | [@username](https://github.com/username) | e.g., Backend, Frontend, UX, Pitcher |
| | | |
| | | |
| | | |

## **Challenge**

*[Which challenge have you decided to compete for?]*

## **Core Idea**

*[What is your rough solution idea?]*

<br>

*[Sketch your technical architecture or data flow to help understand your technical approach. You can edit the mermaid chart below:]*

```mermaid
graph LR;
    subgraph Edge / Hardware
        Sensor[IoT Sensor / Device] -->|MQTT| Gateway[Edge Gateway]
    end
    
    subgraph Cloud / Backend
        Gateway -->|Data Ingestion| API[AWS API Gateway]
        API <--> DB[(MongoDB)]
        API <--> ML[AI/ML Model]
    end
    
    subgraph Client / UI
        API -->|REST / GraphQL| App[Web / Mobile Dashboard]
    end
