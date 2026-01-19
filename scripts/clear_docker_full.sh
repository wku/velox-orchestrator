#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FORCE=false

for arg in "$@"; do
    if [[ "$arg" == "-f" ]] || [[ "$arg" == "--force" ]]; then
        FORCE=true
    fi
done

if [ "$EUID" -ne 0 ] && ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Ошибка: нет доступа к Docker. Проверьте права пользователя или запустите с sudo${NC}"
    exit 1
fi

if [ "$FORCE" = false ]; then
    echo -e "${YELLOW}Внимание: это действие удалит ВСЕ Docker ресурсы безвозвратно${NC}"
    echo "Будут удалены:"
    echo "  - Все контейнеры"
    echo "  - Все образы"
    echo "  - Все тома"
    echo "  - Все пользовательские сети"
    echo "  - Весь build cache"
    echo ""
    read -p "Продолжить? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Отменено"
        exit 0
    fi
fi

echo ""
echo "===== Начало очистки Docker ====="
echo ""

CONTAINERS=$(docker ps -a -q 2>/dev/null)
if [ -n "$CONTAINERS" ]; then
    echo "Останавливаю контейнеры..."
    if docker stop $CONTAINERS 2>/dev/null; then
        echo -e "${GREEN}Контейнеры остановлены${NC}"
    else
        echo -e "${YELLOW}Предупреждение: не все контейнеры остановлены${NC}"
    fi
    
    echo "Удаляю контейнеры..."
    if docker rm -f $CONTAINERS 2>/dev/null; then
        COUNT=$(echo "$CONTAINERS" | wc -w)
        echo -e "${GREEN}Удалено контейнеров: $COUNT${NC}"
    else
        echo -e "${RED}Ошибка при удалении контейнеров${NC}"
    fi
else
    echo "Контейнеры не найдены"
fi

echo ""

VOLUMES=$(docker volume ls -q 2>/dev/null)
if [ -n "$VOLUMES" ]; then
    echo "Удаляю тома..."
    if docker volume rm $VOLUMES 2>/dev/null; then
        COUNT=$(echo "$VOLUMES" | wc -l)
        echo -e "${GREEN}Удалено томов: $COUNT${NC}"
    else
        echo -e "${YELLOW}Предупреждение: не все тома удалены (возможно используются)${NC}"
        docker volume rm $VOLUMES -f 2>/dev/null || true
    fi
else
    echo "Тома не найдены"
fi

echo ""

IMAGES=$(docker images -q 2>/dev/null)
if [ -n "$IMAGES" ]; then
    echo "Удаляю образы..."
    if docker rmi -f $IMAGES 2>/dev/null; then
        COUNT=$(echo "$IMAGES" | wc -w)
        echo -e "${GREEN}Удалено образов: $COUNT${NC}"
    else
        echo -e "${YELLOW}Предупреждение: не все образы удалены${NC}"
    fi
else
    echo "Образы не найдены"
fi

echo ""

NETWORKS=$(docker network ls --filter "type=custom" -q 2>/dev/null)
if [ -n "$NETWORKS" ]; then
    echo "Удаляю пользовательские сети..."
    for net in $NETWORKS; do
        NET_NAME=$(docker network inspect $net --format '{{.Name}}' 2>/dev/null)
        if [[ "$NET_NAME" != "bridge" ]] && [[ "$NET_NAME" != "host" ]] && [[ "$NET_NAME" != "none" ]]; then
            if docker network rm $net 2>/dev/null; then
                echo -e "${GREEN}Удалена сеть: $NET_NAME${NC}"
            else
                echo -e "${YELLOW}Не удалось удалить сеть: $NET_NAME${NC}"
            fi
        fi
    done
else
    echo "Пользовательские сети не найдены"
fi

echo ""

echo "Очищаю build cache..."
if docker builder prune -a -f > /dev/null 2>&1; then
    echo -e "${GREEN}Build cache очищен${NC}"
else
    echo -e "${YELLOW}Предупреждение: не удалось очистить build cache${NC}"
fi

echo ""

echo "Выполняю финальную очистку системы..."
docker system prune -a -f --volumes > /dev/null 2>&1 || true

echo ""
echo "===== Очистка завершена ====="
echo ""

echo "Статус использования диска после очистки:"
docker system df

echo ""
echo -e "${GREEN}Все Docker ресурсы успешно удалены${NC}"
